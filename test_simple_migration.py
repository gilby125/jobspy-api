#!/usr/bin/env python3
"""
Simple test script for the migration functionality using raw SQL.
"""
import os
import sys
import asyncio
import pandas as pd
from datetime import datetime

# Set environment variables
os.environ['DATABASE_URL'] = 'postgresql://jobspy:jobspy_password@localhost:5432/jobspy'
os.environ['REDIS_URL'] = 'redis://localhost:6379'

# Add current directory to path
sys.path.insert(0, '.')

from app.services.job_service import JobService
from app.services.deduplication_service import deduplication_service
from app.db.database import init_database
from sqlalchemy import text

async def test_simple_migration():
    """Test simple migration with direct SQL approach."""
    print("🔍 Testing Simple Migration...")
    
    # Initialize database
    init_database()
    from app.db.database import SessionLocal
    
    # Test 1: Search for jobs
    print("\n1. Searching for jobs using JobSpy...")
    
    search_params = {
        'site_name': ['indeed'],
        'search_term': 'python developer',
        'location': 'San Francisco, CA',
        'results_wanted': 3,  # Very small number for testing
        'hours_old': 24,
        'country_indeed': 'USA'
    }
    
    try:
        jobs_df, is_cached = await JobService.search_jobs(search_params)
        print(f"   ✅ Found {len(jobs_df)} jobs (cached: {is_cached})")
        
        if len(jobs_df) > 0:
            print(f"   Sample job: {jobs_df.iloc[0]['title']} at {jobs_df.iloc[0]['company']}")
            
            # Print column names for debugging
            print(f"   DataFrame columns: {list(jobs_df.columns)}")
        
    except Exception as e:
        print(f"   ❌ Job search failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Manual migration using raw SQL
    print("\n2. Manually migrating jobs using raw SQL...")
    
    if len(jobs_df) > 0:
        try:
            with SessionLocal() as db:
                jobs_inserted = 0
                
                for _, job_data in jobs_df.iterrows():
                    # Generate job hash (handle NaN values)
                    def safe_str(value):
                        if pd.isna(value):
                            return ''
                        return str(value)
                    
                    job_dict = {
                        'title': safe_str(job_data.get('title', '')),
                        'company': safe_str(job_data.get('company', '')),
                        'location': safe_str(job_data.get('location', '')),
                        'job_type': safe_str(job_data.get('job_type', '')),
                        'description': safe_str(job_data.get('description', ''))
                    }
                    
                    job_hash = deduplication_service.generate_job_hash(job_dict)
                    print(f"   Generated hash for '{job_data.get('title', 'Unknown')}': {job_hash[:16]}...")
                    
                    # Check if job already exists
                    existing = db.execute(text("""
                        SELECT id FROM temp_job_postings WHERE job_hash = :job_hash
                    """), {'job_hash': job_hash}).fetchone()
                    
                    if existing:
                        print(f"   Job already exists (duplicate): {job_data.get('title', 'Unknown')}")
                        continue
                    
                    # Insert company
                    company_result = db.execute(text("""
                        INSERT INTO temp_companies (name, created_at) 
                        VALUES (:name, :created_at)
                        ON CONFLICT (name, domain) DO UPDATE SET name = EXCLUDED.name
                        RETURNING id
                    """), {
                        'name': safe_str(job_data.get('company', 'Unknown Company')),
                        'created_at': datetime.utcnow()
                    })
                    company_id = company_result.scalar()
                    
                    # Insert location (if not remote)
                    location_id = None
                    location_str = safe_str(job_data.get('location', ''))
                    if location_str and location_str.lower() not in ['remote', 'work from home']:
                        parts = location_str.split(',')
                        city = parts[0].strip() if parts else ''
                        state = parts[1].strip() if len(parts) > 1 else ''
                        
                        location_result = db.execute(text("""
                            INSERT INTO temp_locations (city, state, country, created_at) 
                            VALUES (:city, :state, :country, :created_at)
                            ON CONFLICT (city, state, country) DO UPDATE SET city = EXCLUDED.city
                            RETURNING id
                        """), {
                            'city': city,
                            'state': state,
                            'country': 'USA',
                            'created_at': datetime.utcnow()
                        })
                        location_id = location_result.scalar()
                    
                    # Insert job posting
                    job_result = db.execute(text("""
                        INSERT INTO temp_job_postings (
                            job_hash, title, company_id, location_id,
                            job_type, is_remote, description,
                            salary_min, salary_max, salary_currency,
                            first_seen_at, last_seen_at, status,
                            created_at, updated_at
                        ) VALUES (
                            :job_hash, :title, :company_id, :location_id,
                            :job_type, :is_remote, :description,
                            :salary_min, :salary_max, :salary_currency,
                            :first_seen_at, :last_seen_at, :status,
                            :created_at, :updated_at
                        ) RETURNING id
                    """), {
                        'job_hash': job_hash,
                        'title': safe_str(job_data.get('title', '')),
                        'company_id': company_id,
                        'location_id': location_id,
                        'job_type': safe_str(job_data.get('job_type')),
                        'is_remote': 'remote' in safe_str(job_data.get('location', '')).lower(),
                        'description': safe_str(job_data.get('description', '')),
                        'salary_min': job_data.get('min_amount') if pd.notna(job_data.get('min_amount')) else None,
                        'salary_max': job_data.get('max_amount') if pd.notna(job_data.get('max_amount')) else None,
                        'salary_currency': safe_str(job_data.get('currency', 'USD')),
                        'first_seen_at': datetime.utcnow(),
                        'last_seen_at': datetime.utcnow(),
                        'status': 'active',
                        'created_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    })
                    job_posting_id = job_result.scalar()
                    
                    # Insert job source
                    db.execute(text("""
                        INSERT INTO temp_job_sources (
                            job_posting_id, source_site, external_job_id,
                            job_url, easy_apply, created_at, updated_at
                        ) VALUES (
                            :job_posting_id, :source_site, :external_job_id,
                            :job_url, :easy_apply, :created_at, :updated_at
                        )
                    """), {
                        'job_posting_id': job_posting_id,
                        'source_site': safe_str(job_data.get('site', 'indeed')),
                        'external_job_id': safe_str(job_data.get('id')),  # Note: using 'id' not 'job_id'
                        'job_url': safe_str(job_data.get('job_url', '')),
                        'easy_apply': bool(job_data.get('easy_apply', False)) if pd.notna(job_data.get('easy_apply')) else False,
                        'created_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    })
                    
                    # Insert job metrics
                    db.execute(text("""
                        INSERT INTO temp_job_metrics (
                            job_posting_id, total_seen_count, sites_posted_count,
                            days_active, repost_count, last_activity_date,
                            created_at, updated_at
                        ) VALUES (
                            :job_posting_id, :total_seen_count, :sites_posted_count,
                            :days_active, :repost_count, :last_activity_date,
                            :created_at, :updated_at
                        )
                    """), {
                        'job_posting_id': job_posting_id,
                        'total_seen_count': 1,
                        'sites_posted_count': 1,
                        'days_active': 0,
                        'repost_count': 0,
                        'last_activity_date': datetime.utcnow().date(),
                        'created_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    })
                    
                    jobs_inserted += 1
                    print(f"   ✅ Inserted job: {safe_str(job_data.get('title', 'Unknown'))}")
                
                db.commit()
                print(f"   ✅ Successfully inserted {jobs_inserted} jobs")
                
        except Exception as e:
            print(f"   ❌ Manual migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # Test 3: Verify data
    print("\n3. Verifying migrated data...")
    
    try:
        with SessionLocal() as db:
            # Check counts
            job_count = db.execute(text("SELECT COUNT(*) FROM temp_job_postings")).scalar()
            company_count = db.execute(text("SELECT COUNT(*) FROM temp_companies")).scalar()
            source_count = db.execute(text("SELECT COUNT(*) FROM temp_job_sources")).scalar()
            metrics_count = db.execute(text("SELECT COUNT(*) FROM temp_job_metrics")).scalar()
            
            print(f"   ✅ Data verification:")
            print(f"      - Jobs: {job_count}")
            print(f"      - Companies: {company_count}")
            print(f"      - Sources: {source_count}")
            print(f"      - Metrics: {metrics_count}")
            
            # Show sample data
            if job_count > 0:
                sample = db.execute(text("""
                    SELECT jp.job_hash, jp.title, c.name as company_name,
                           js.source_site, jm.total_seen_count
                    FROM temp_job_postings jp
                    JOIN temp_companies c ON jp.company_id = c.id
                    JOIN temp_job_sources js ON jp.id = js.job_posting_id
                    JOIN temp_job_metrics jm ON jp.id = jm.job_posting_id
                    LIMIT 1
                """)).fetchone()
                
                print(f"   📋 Sample migrated job:")
                print(f"      - Hash: {sample.job_hash[:16]}...")
                print(f"      - Title: {sample.title}")
                print(f"      - Company: {sample.company_name}")
                print(f"      - Source: {sample.source_site}")
                print(f"      - Seen count: {sample.total_seen_count}")
                
    except Exception as e:
        print(f"   ❌ Data verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✨ Simple migration test completed successfully!")
    return True

async def main():
    """Main test function."""
    print("🚀 Simple JobSpy Migration Test")
    print("=" * 50)
    
    success = await test_simple_migration()
    
    if success:
        print("\n🎉 Simple migration testing completed successfully!")
        print("\nThe temp_ tables now contain migrated data.")
        print("You can run the full migration script to process larger datasets.")
    else:
        print("\n❌ Simple migration testing failed!")

if __name__ == "__main__":
    asyncio.run(main())