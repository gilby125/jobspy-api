"""Job search service layer."""
from typing import Dict, Any, Tuple, List
import pandas as pd
from jobspy import scrape_jobs
import logging

from app.core.config import settings
from app.cache import cache
from app.services.job_tracking_service import job_tracking_service

logger = logging.getLogger(__name__)

class JobService:
    """Service for interacting with JobSpy library and job tracking."""
    
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
    async def save_jobs_to_database(jobs_df: pd.DataFrame, search_params: Dict[str, Any], db) -> Dict[str, Any]:
        """
        Save jobs from DataFrame to database using the job tracking service.
        
        Args:
            jobs_df: DataFrame containing job results
            search_params: Search parameters used
            db: Database session
            
        Returns:
            Dictionary with processing statistics
        """
        if jobs_df.empty:
            return {
                'total_jobs': 0,
                'new_jobs': 0,
                'duplicate_jobs': 0,
                'updated_jobs': 0,
                'errors': 0,
                'new_companies': 0
            }
        
        # Convert DataFrame to list of dictionaries for processing
        jobs_data = jobs_df.to_dict('records')
        
        # Extract source site from search params
        site_names = search_params.get("site_name", search_params.get("site_names", ["indeed"]))
        if isinstance(site_names, list):
            # Process each site's jobs separately for accurate tracking
            all_stats = {
                'total_jobs': 0,
                'new_jobs': 0,
                'duplicate_jobs': 0,
                'updated_jobs': 0,
                'errors': 0,
                'new_companies': 0,
                'processed_jobs': []
            }
            
            for site in site_names:
                # Filter jobs for this site
                site_jobs = [job for job in jobs_data if self._safe_str(job.get('site', '')).lower() == site.lower()]
                
                if site_jobs:
                    # Process jobs through the tracking service
                    stats = job_tracking_service.process_scraped_jobs(
                        jobs_data=site_jobs,
                        source_site=site,
                        search_params=search_params,
                        db=db
                    )
                    
                    # Aggregate stats
                    all_stats['total_jobs'] += stats['total_jobs']
                    all_stats['new_jobs'] += stats['new_jobs']
                    all_stats['duplicate_jobs'] += stats['duplicate_jobs']
                    all_stats['updated_jobs'] += stats['updated_jobs']
                    all_stats['errors'] += stats['errors']
                    all_stats['new_companies'] += stats['new_companies']
                    all_stats['processed_jobs'].extend(stats.get('processed_jobs', []))
            
            return all_stats
        else:
            # Single site processing
            return job_tracking_service.process_scraped_jobs(
                jobs_data=jobs_data,
                source_site=str(site_names),
                search_params=search_params,
                db=db
            )

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
    
    @staticmethod
    def _safe_str(value: Any) -> str:
        """Safely convert any value to string, handling NaN values."""
        if value is None:
            return ''
        
        # Handle NaN values from pandas
        import math
        if isinstance(value, float) and math.isnan(value):
            return ''
        
        return str(value)
