#!/usr/bin/env python3
"""
Test script for the job search and migration functionality.
"""
import os
import sys
import json
import requests
import asyncio
import pandas as pd
from datetime import datetime

# Set environment variables
os.environ['DATABASE_URL'] = 'postgresql://jobspy:jobspy_password@localhost:5432/jobspy'
os.environ['REDIS_URL'] = 'redis://localhost:6379'

# Add current directory to path
sys.path.insert(0, '.')

from app.services.job_service import JobService
from app.db.database import SessionLocal, init_database
from sqlalchemy import text

async def test_job_search_and_migration():
    """Test job search and migration functionality."""
    print("🔍 Testing Job Search and Migration...")
    
    # Initialize database
    init_database()
    
    # Test 1: Search for a small number of jobs
    print("\n1. Searching for jobs using JobSpy...")
    
    search_params = {
        'site_name': ['indeed'],
        'search_term': 'python developer',
        'location': 'San Francisco, CA',
        'results_wanted': 5,  # Small number for testing
        'hours_old': 24,
        'country_indeed': 'USA'
    }
    
    try:
        jobs_df, is_cached = await JobService.search_jobs(search_params)
        print(f"   ✅ Found {len(jobs_df)} jobs (cached: {is_cached})")
        
        if len(jobs_df) > 0:
            print(f"   Sample job: {jobs_df.iloc[0]['title']} at {jobs_df.iloc[0]['company']}")
        
    except Exception as e:
        print(f"   ❌ Job search failed: {e}")
        return False
    
    # Test 2: Save jobs to database using new tracking system
    print("\n2. Saving jobs to database using job tracking service...")
    
    if len(jobs_df) > 0:
        try:
            with SessionLocal() as db:
                stats = await JobService.save_jobs_to_database(jobs_df, search_params, db)
                print(f"   ✅ Migration stats:")
                print(f"      - Total jobs: {stats['total_jobs']}")
                print(f"      - New jobs: {stats['new_jobs']}")
                print(f"      - Duplicate jobs: {stats['duplicate_jobs']}")
                print(f"      - Updated jobs: {stats['updated_jobs']}")
                print(f"      - Errors: {stats['errors']}")
                print(f"      - New companies: {stats['new_companies']}")
                
        except Exception as e:
            print(f"   ❌ Job saving failed: {e}")
            return False
    
    # Test 3: Verify data in tracking tables
    print("\n3. Verifying data in tracking tables...")
    
    try:
        with SessionLocal() as db:
            # Check temp tables
            job_count = db.execute(text("SELECT COUNT(*) FROM temp_job_postings")).scalar()
            company_count = db.execute(text("SELECT COUNT(*) FROM temp_companies")).scalar()
            source_count = db.execute(text("SELECT COUNT(*) FROM temp_job_sources")).scalar()
            metrics_count = db.execute(text("SELECT COUNT(*) FROM temp_job_metrics")).scalar()
            
            print(f"   ✅ Data verification:")
            print(f"      - Jobs: {job_count}")
            print(f"      - Companies: {company_count}")
            print(f"      - Sources: {source_count}")
            print(f"      - Metrics: {metrics_count}")
            
            # Check for deduplication
            if job_count > 0:
                sample_job = db.execute(text("""
                    SELECT jp.job_hash, jp.title, c.name as company_name, 
                           jm.sites_posted_count, jm.total_seen_count
                    FROM temp_job_postings jp 
                    JOIN temp_companies c ON jp.company_id = c.id
                    LEFT JOIN temp_job_metrics jm ON jp.id = jm.job_posting_id
                    LIMIT 1
                """)).fetchone()
                
                print(f"   📋 Sample job:")
                print(f"      - Hash: {sample_job.job_hash[:16]}...")
                print(f"      - Title: {sample_job.title}")
                print(f"      - Company: {sample_job.company_name}")
                print(f"      - Sites posted: {sample_job.sites_posted_count}")
                print(f"      - Total seen: {sample_job.total_seen_count}")
                
    except Exception as e:
        print(f"   ❌ Data verification failed: {e}")
        return False
    
    # Test 4: Test deduplication by searching again
    print("\n4. Testing deduplication with repeat search...")
    
    try:
        jobs_df2, is_cached2 = await JobService.search_jobs(search_params)
        
        if not is_cached2 and len(jobs_df2) > 0:
            with SessionLocal() as db:
                stats2 = await JobService.save_jobs_to_database(jobs_df2, search_params, db)
                print(f"   ✅ Second search stats:")
                print(f"      - Total jobs: {stats2['total_jobs']}")
                print(f"      - New jobs: {stats2['new_jobs']}")
                print(f"      - Duplicate jobs: {stats2['duplicate_jobs']}")
                print(f"      - Updated jobs: {stats2['updated_jobs']}")
                
                # Check final counts
                job_count_final = db.execute(text("SELECT COUNT(*) FROM temp_job_postings")).scalar()
                print(f"   📊 Final job count: {job_count_final}")
                
    except Exception as e:
        print(f"   ❌ Deduplication test failed: {e}")
        return False
    
    print("\n✨ All tests completed successfully!")
    return True

def test_api_endpoints():
    """Test API endpoints to ensure they work with the new schema."""
    print("\n🌐 Testing API endpoints...")
    
    # Start API server
    import subprocess
    import time
    
    api_process = subprocess.Popen([
        'python', '-m', 'uvicorn', 'app.main:app', 
        '--host', '0.0.0.0', '--port', '8787'
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server to start
    time.sleep(3)
    
    try:
        # Test health endpoint
        response = requests.get('http://localhost:8787/health', timeout=5)
        if response.status_code == 200:
            print("   ✅ Health endpoint working")
        else:
            print(f"   ❌ Health endpoint failed: {response.status_code}")
        
        # Test search endpoint (using tracking routes)
        # Note: This would require updating main.py to include the tracking routes
        print("   ℹ️  Search endpoint test requires switching to tracking routes in main.py")
        
    except requests.exceptions.RequestException as e:
        print(f"   ❌ API test failed: {e}")
    finally:
        # Stop the server
        api_process.terminate()
        api_process.wait()

async def main():
    """Main test function."""
    print("🚀 JobSpy Migration Test Suite")
    print("=" * 50)
    
    # Test the job search and migration
    success = await test_job_search_and_migration()
    
    if success:
        # Test API endpoints
        test_api_endpoints()
        print("\n🎉 Migration testing completed successfully!")
        print("\nNext steps:")
        print("1. Review the data in temp_ tables")
        print("2. Run finalization: python scripts/run_migration.py --finalize")
        print("3. Update main.py to use jobs_tracking routes")
    else:
        print("\n❌ Migration testing failed!")

if __name__ == "__main__":
    asyncio.run(main())