"""Job search service layer."""
from typing import Dict, Any, Tuple
import pandas as pd
from jobspy import scrape_jobs
import logging

from app.core.config import settings
from app.cache import cache

logger = logging.getLogger(__name__)

class JobService:
    """Service for interacting with JobSpy library."""
    
    @staticmethod
    async def search_jobs(params: Dict[str, Any]) -> Tuple[pd.DataFrame, bool]:
        """
        Execute a job search using the JobSpy library.
        
        Args:
            params: Dictionary of search parameters
            
        Returns:
            Tuple of (DataFrame containing job results, is_cached boolean)
        """
        # Apply default proxies from env if none provided
        if params.get('proxies') is None and settings.default_proxies_list:
            params['proxies'] = settings.default_proxies_list
        
        # Apply default CA cert path if none provided
        if params.get('ca_cert') is None and settings.CA_CERT_PATH:
            params['ca_cert'] = settings.CA_CERT_PATH
            
        # Apply default country_indeed if none provided
        if params.get('country_indeed') is None and settings.DEFAULT_COUNTRY_INDEED:
            params['country_indeed'] = settings.DEFAULT_COUNTRY_INDEED
        
        # Check cache first
        cached_results = await cache.get(params)
        if cached_results is not None:
            logger.info(f"Returning cached results with {len(cached_results)} jobs")
            return cached_results, True
        
        # Execute search
        jobs_df = scrape_jobs(**params)
        
        # Cache the results
        await cache.set(params, jobs_df)
        
        return jobs_df, False

    @staticmethod
    async def save_jobs_to_database(jobs_df: pd.DataFrame, search_params: Dict[str, Any], db, scraping_run_id: int = None) -> int:
        """
        Save jobs from DataFrame to database.
        
        Args:
            jobs_df: DataFrame containing job results
            search_params: Search parameters used
            db: Database session
            
        Returns:
            Number of jobs successfully inserted
        """
        if jobs_df.empty:
            return 0
            
        from datetime import datetime
        from sqlalchemy import text
        import json
        
        # Helper function to parse date_posted
        def parse_date_posted(date_str):
            if not date_str:
                return None
            try:
                from datetime import datetime
                # Try common date formats
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                    try:
                        return datetime.strptime(str(date_str), fmt).date()
                    except ValueError:
                        continue
                return None
            except:
                return None
        
        try:
            # Create or use existing scraping run record
            if scraping_run_id is None:
                # Create a new scraping run record for tracking (for direct API calls)
                site_names = search_params.get("site_name", search_params.get("site_names", ["indeed"]))
                search_terms_array = f"ARRAY['{search_params.get('search_term', '')}']" if search_params.get('search_term') else "ARRAY[]::varchar[]"
                locations_array = f"ARRAY['{search_params.get('location', '')}']" if search_params.get('location') else "ARRAY[]::varchar[]"
                
                result = db.execute(text(f"""
                    INSERT INTO scraping_runs (source_platform, search_terms, locations, start_time, 
                                             status, jobs_found, jobs_processed, jobs_skipped, 
                                             error_count, config_used)
                    VALUES (:source_platform, {search_terms_array}, {locations_array}, :start_time, 
                            :status, :jobs_found, :jobs_processed, :jobs_skipped, 
                            :error_count, :config_used)
                    RETURNING id
                """), {
                    "source_platform": ",".join(site_names) if isinstance(site_names, list) else str(site_names),
                    "start_time": datetime.now(),
                    "status": "completed",
                    "jobs_found": len(jobs_df),
                    "jobs_processed": 0,  # We'll update this as we insert jobs
                    "jobs_skipped": 0,
                    "error_count": 0,
                    "config_used": json.dumps(search_params)
                })
                scraping_run_id = result.fetchone()[0]
            
            # Process jobs and save to database
            jobs_data = jobs_df.to_dict('records')
            jobs_inserted = 0
            
            for job_data in jobs_data:
                try:
                    # Create/find company
                    company_result = db.execute(text("""
                        INSERT INTO companies (name, domain, created_at) 
                        VALUES (:name, :domain, :created_at)
                        ON CONFLICT (name, domain) DO UPDATE SET name = EXCLUDED.name
                        RETURNING id
                    """), {
                        "name": job_data.get('company', 'Unknown Company'),
                        "domain": None,  # Set domain to NULL for now
                        "created_at": datetime.now()
                    })
                    company_id = company_result.fetchone()[0]
                    
                    # Create/find location  
                    location_parts = job_data.get('location', '').split(',')
                    city = location_parts[0].strip() if location_parts else ''
                    state = location_parts[1].strip() if len(location_parts) > 1 else ''
                    
                    location_result = db.execute(text("""
                        INSERT INTO locations (city, state, country, created_at) 
                        VALUES (:city, :state, :country, :created_at)
                        ON CONFLICT (city, state, country) DO UPDATE SET city = EXCLUDED.city
                        RETURNING id
                    """), {
                        "city": city,
                        "state": state,
                        "country": "USA",
                        "created_at": datetime.now()
                    })
                    location_id = location_result.fetchone()[0]
                    
                    # Insert job posting
                    job_result = db.execute(text("""
                        INSERT INTO job_postings (
                            external_id, title, company_id, location_id, description,
                            job_type, salary_min, salary_max, salary_currency, 
                            is_remote, job_url, source_platform, date_posted, 
                            date_scraped, last_seen, is_active
                        ) VALUES (
                            :external_id, :title, :company_id, :location_id, :description, 
                            :job_type, :salary_min, :salary_max, :salary_currency,
                            :is_remote, :job_url, :source_platform, :date_posted,
                            :date_scraped, :last_seen, :is_active
                        )
                        ON CONFLICT (external_id, source_platform) DO UPDATE SET
                            last_seen = :last_seen,
                            is_active = :is_active
                        RETURNING id
                    """), {
                        "external_id": job_data.get('id', ''),
                        "title": job_data.get('title', '')[:255],  # Limit length
                        "company_id": company_id,
                        "location_id": location_id,
                        "description": job_data.get('description', ''),
                        "job_type": job_data.get('job_type'),
                        "salary_min": job_data.get('min_amount'),
                        "salary_max": job_data.get('max_amount'), 
                        "salary_currency": job_data.get('currency', 'USD'),
                        "is_remote": job_data.get('is_remote', False),
                        "job_url": job_data.get('job_url', ''),
                        "source_platform": job_data.get('site', ''),
                        "date_posted": parse_date_posted(job_data.get('date_posted')),
                        "date_scraped": datetime.now(),
                        "last_seen": datetime.now(),
                        "is_active": True
                    })
                    jobs_inserted += 1
                        
                except Exception as job_error:
                    logger.warning(f"Failed to insert job {job_data.get('title', 'Unknown')}: {job_error}")
                    continue
            
            # Update the scraping run with final stats
            db.execute(text("""
                UPDATE scraping_runs 
                SET jobs_processed = :jobs_processed, end_time = :end_time
                WHERE id = :id
            """), {
                "jobs_processed": jobs_inserted,
                "end_time": datetime.now(),
                "id": scraping_run_id
            })
            
            db.commit()
            logger.info(f"Saved {jobs_inserted} jobs to database")
            return jobs_inserted
                    
        except Exception as e:
            logger.error(f"Error saving jobs to database: {e}")
            db.rollback()
            return 0

    @staticmethod
    def filter_jobs(jobs_df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
        """Filter job results based on criteria."""
        filtered_df = jobs_df.copy()
        
        # Filter by salary range
        if 'min_salary' in filters and filters['min_salary'] is not None:
            # Convert to numeric first to handle comparison properly
            filtered_df = filtered_df[filtered_df['MIN_AMOUNT'].astype(float) >= float(filters['min_salary'])]
            
        if 'max_salary' in filters and filters['max_salary'] is not None:
            filtered_df = filtered_df[filtered_df['MAX_AMOUNT'].astype(float) <= float(filters['max_salary'])]
            
        # Filter by company
        if 'company' in filters and filters['company']:
            filtered_df = filtered_df[filtered_df['COMPANY'].str.contains(filters['company'], case=False, na=False)]
            
        # Filter by job type
        if 'job_type' in filters and filters['job_type']:
            filtered_df = filtered_df[filtered_df['JOB_TYPE'] == filters['job_type']]
            
        # Filter by location
        if 'city' in filters and filters['city']:
            filtered_df = filtered_df[filtered_df['CITY'].str.contains(filters['city'], case=False, na=False)]
            
        if 'state' in filters and filters['state']:
            filtered_df = filtered_df[filtered_df['STATE'].str.contains(filters['state'], case=False, na=False)]
            
        # Filter by keyword in title
        if 'title_keywords' in filters and filters['title_keywords']:
            filtered_df = filtered_df[filtered_df['TITLE'].str.contains(filters['title_keywords'], case=False, na=False)]
            
        return filtered_df
    
    @staticmethod
    def sort_jobs(jobs_df: pd.DataFrame, sort_by: str, sort_order: str = 'desc') -> pd.DataFrame:
        """Sort job results by specified field."""
        if not sort_by or sort_by not in jobs_df.columns:
            return jobs_df
            
        ascending = sort_order.lower() != 'desc'
        return jobs_df.sort_values(by=sort_by, ascending=ascending)
