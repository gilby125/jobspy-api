"""
Hybrid job service that uses Go workers when available, falls back to Python JobSpy.
This service orchestrates the transition from Python-only to hybrid Python+Go architecture.
"""
import asyncio
import logging
import time
from typing import Dict, Any, Tuple, Optional, List
import pandas as pd
from datetime import datetime, timezone

from app.services.job_service import JobService
from app.workers.orchestrator import orchestrator
from app.workers.message_protocol import ScraperType
from app.services.job_tracking_service import job_tracking_service
from app.db.database import get_db
from app.config import settings
from app.cache import cache

logger = logging.getLogger(__name__)


class HybridJobService:
    """
    Hybrid service that intelligently routes job searches between Go workers and Python JobSpy.
    
    This service provides a seamless transition path:
    - Uses Go workers for supported sites when workers are healthy
    - Falls back to Python JobSpy when needed
    - Integrates with job tracking and deduplication
    - Provides unified caching and response format
    """
    
    def __init__(self):
        self.go_worker_enabled = True  # Can be configured via environment
        self.fallback_to_python = True
        self.worker_timeout = 30  # seconds to wait for Go worker response
        
        # Site support mapping
        self.go_supported_sites = {'indeed'}  # Only Indeed implemented in Go currently
        self.python_supported_sites = {
            'indeed', 'linkedin', 'zip_recruiter', 'glassdoor', 
            'google', 'bayt', 'naukri'
        }
    
    async def search_jobs(self, params: Dict[str, Any]) -> Tuple[pd.DataFrame, bool]:
        """
        Execute hybrid job search using both Go workers and Python JobSpy.
        
        Args:
            params: Search parameters dictionary
            
        Returns:
            Tuple of (DataFrame with results, is_cached)
        """
        start_time = time.time()
        request_sites = params.get('site_name', settings.DEFAULT_SITE_NAMES)
        
        # Normalize site names to list
        if isinstance(request_sites, str):
            request_sites = [request_sites]
        
        logger.info(f"Starting hybrid search for sites: {request_sites}")
        
        # Check cache first for the entire request
        cache_key = self._generate_cache_key(params)
        cached_result = await cache.get(cache_key) if settings.ENABLE_CACHE else None
        if cached_result:
            logger.info(f"Returning cached results with {len(cached_result)} jobs")
            return cached_result, True
        
        # Determine routing strategy
        go_sites, python_sites = self._route_sites(request_sites)
        
        # Execute searches concurrently
        all_results = []
        tasks = []
        
        # Start Go worker tasks
        if go_sites and self.go_worker_enabled:
            for site in go_sites:
                task = asyncio.create_task(
                    self._search_with_go_worker(site, params),
                    name=f"go_worker_{site}"
                )
                tasks.append(task)
        
        # Start Python JobSpy task for remaining sites
        if python_sites:
            task = asyncio.create_task(
                self._search_with_python_jobspy(python_sites, params),
                name="python_jobspy"
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and handle exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Task {tasks[i].get_name()} failed: {result}")
                    # Handle fallback if Go worker fails
                    if tasks[i].get_name().startswith("go_worker_"):
                        site = tasks[i].get_name().split("_")[-1]
                        if self.fallback_to_python and site in self.python_supported_sites:
                            logger.info(f"Falling back to Python JobSpy for {site}")
                            fallback_result = await self._search_with_python_jobspy([site], params)
                            if fallback_result is not None:
                                all_results.append(fallback_result)
                else:
                    if result is not None:
                        all_results.append(result)
        
        # Combine all results
        if not all_results:
            logger.warning("No results from any search method")
            return pd.DataFrame(), False
        
        # Combine DataFrames
        combined_df = pd.concat(all_results, ignore_index=True) if len(all_results) > 1 else all_results[0]
        
        # Remove duplicates based on job URL or title+company
        combined_df = self._deduplicate_results(combined_df)
        
        # Cache combined results
        if settings.ENABLE_CACHE:
            await cache.set(cache_key, combined_df, expire=settings.CACHE_EXPIRY)
        
        execution_time = time.time() - start_time
        logger.info(f"Hybrid search completed in {execution_time:.2f}s. "
                   f"Found {len(combined_df)} jobs from {len(request_sites)} sites")
        
        return combined_df, False
    
    def _route_sites(self, requested_sites: List[str]) -> Tuple[List[str], List[str]]:
        """
        Route sites between Go workers and Python JobSpy based on availability and health.
        
        Args:
            requested_sites: List of site names to search
            
        Returns:
            Tuple of (go_sites, python_sites)
        """
        go_sites = []
        python_sites = []
        
        if not self.go_worker_enabled:
            return [], requested_sites
        
        # Check Go worker health
        healthy_go_workers = self._check_go_worker_health()
        
        for site in requested_sites:
            site_lower = site.lower()
            
            # Route to Go if supported and workers are healthy
            if (site_lower in self.go_supported_sites and 
                site_lower in healthy_go_workers):
                go_sites.append(site_lower)
            else:
                python_sites.append(site)
        
        logger.debug(f"Site routing: Go workers={go_sites}, Python JobSpy={python_sites}")
        return go_sites, python_sites
    
    def _check_go_worker_health(self) -> set:
        """
        Check health of Go workers and return set of healthy scraper types.
        
        Returns:
            Set of healthy scraper type names
        """
        try:
            health_statuses = orchestrator.get_scraper_health()
            healthy_scrapers = set()
            
            for status in health_statuses:
                if status['status'] == 'healthy':
                    healthy_scrapers.add(status['scraper_type'])
            
            logger.debug(f"Healthy Go workers: {healthy_scrapers}")
            return healthy_scrapers
            
        except Exception as e:
            logger.warning(f"Could not check Go worker health: {e}")
            return set()
    
    async def _search_with_go_worker(self, site: str, params: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        Execute search using Go workers.
        
        Args:
            site: Site name to search
            params: Search parameters
            
        Returns:
            DataFrame with results or None if failed
        """
        try:
            logger.info(f"Starting Go worker search for {site}")
            
            # Create task for specific site
            site_params = params.copy()
            site_params['site_name'] = [site]
            
            # Create and submit task
            scraper_type = ScraperType(site.lower())
            task = orchestrator.create_scraping_task(scraper_type, site_params)
            
            success = orchestrator.submit_scraping_task(task)
            if not success:
                logger.error(f"Failed to submit Go worker task for {site}")
                return None
            
            # Wait for results with timeout
            start_time = time.time()
            while time.time() - start_time < self.worker_timeout:
                result = orchestrator.process_scraping_results(timeout=1)
                if result and result['task_id'] == task.task_id:
                    # Convert job data to DataFrame
                    return self._convert_go_results_to_dataframe(result)
                
                await asyncio.sleep(0.5)  # Small delay between checks
            
            logger.warning(f"Go worker search for {site} timed out after {self.worker_timeout}s")
            return None
            
        except Exception as e:
            logger.error(f"Go worker search failed for {site}: {e}")
            return None
    
    async def _search_with_python_jobspy(self, sites: List[str], params: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        Execute search using Python JobSpy library.
        
        Args:
            sites: List of site names to search
            params: Search parameters
            
        Returns:
            DataFrame with results or None if failed
        """
        try:
            logger.info(f"Starting Python JobSpy search for sites: {sites}")
            
            # Prepare parameters for JobSpy
            jobspy_params = params.copy()
            jobspy_params['site_name'] = sites
            
            # Execute search in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            jobs_df, _ = await loop.run_in_executor(
                None, 
                JobService.search_jobs, 
                jobspy_params
            )
            
            logger.info(f"Python JobSpy found {len(jobs_df)} jobs for sites: {sites}")
            return jobs_df
            
        except Exception as e:
            logger.error(f"Python JobSpy search failed for sites {sites}: {e}")
            return None
    
    def _convert_go_results_to_dataframe(self, go_result: Dict) -> pd.DataFrame:
        """
        Convert Go worker results to DataFrame format compatible with Python JobSpy.
        
        Args:
            go_result: Result dictionary from Go worker
            
        Returns:
            DataFrame in JobSpy format
        """
        try:
            jobs_data = []
            
            for job in go_result.get('jobs_data', []):
                # Map Go worker job format to JobSpy DataFrame format
                job_dict = {
                    'TITLE': job.get('title', ''),
                    'COMPANY': job.get('company', ''),
                    'LOCATION': job.get('location', ''),
                    'JOB_URL': job.get('job_url', ''),
                    'DESCRIPTION': job.get('description', ''),
                    'MIN_AMOUNT': job.get('salary_min'),
                    'MAX_AMOUNT': job.get('salary_max'),
                    'CURRENCY': job.get('salary_currency', 'USD'),
                    'JOB_TYPE': job.get('job_type'),
                    'IS_REMOTE': job.get('is_remote', False),
                    'DATE_POSTED': job.get('posted_date'),
                    'EASY_APPLY': job.get('easy_apply', False),
                    'SITE': go_result.get('scraper_type', '').upper(),
                    'JOB_URL_DIRECT': job.get('apply_url'),
                    'COMPANY_LOGO': job.get('company_logo'),
                    'SKILLS': ', '.join(job.get('skills', [])) if job.get('skills') else None,
                    'BENEFITS': ', '.join(job.get('benefits', [])) if job.get('benefits') else None
                }
                jobs_data.append(job_dict)
            
            df = pd.DataFrame(jobs_data)
            logger.debug(f"Converted {len(df)} Go worker jobs to DataFrame")
            return df
            
        except Exception as e:
            logger.error(f"Failed to convert Go results to DataFrame: {e}")
            return pd.DataFrame()
    
    def _deduplicate_results(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove duplicate jobs from combined results.
        
        Args:
            df: DataFrame with potentially duplicate jobs
            
        Returns:
            DataFrame with duplicates removed
        """
        if df.empty:
            return df
        
        # Remove exact URL duplicates first
        initial_count = len(df)
        df = df.drop_duplicates(subset=['JOB_URL'], keep='first')
        
        # Remove title+company duplicates
        df = df.drop_duplicates(subset=['TITLE', 'COMPANY'], keep='first')
        
        final_count = len(df)
        if initial_count != final_count:
            logger.info(f"Removed {initial_count - final_count} duplicate jobs")
        
        return df
    
    def _generate_cache_key(self, params: Dict[str, Any]) -> str:
        """Generate cache key for parameters."""
        # Create a stable cache key from parameters
        cache_params = {k: v for k, v in params.items() if v is not None}
        # Sort to ensure consistent key
        sorted_params = sorted(cache_params.items())
        return f"hybrid_search:{hash(str(sorted_params))}"
    
    async def get_scraper_status(self) -> Dict[str, Any]:
        """
        Get status of all scrapers (Go workers and Python JobSpy availability).
        
        Returns:
            Dictionary with scraper status information
        """
        try:
            # Get Go worker health
            go_health = orchestrator.get_scraper_health()
            queue_status = orchestrator.get_queue_status()
            
            # Check Python JobSpy (always available if imported successfully)
            python_available = True
            try:
                from jobspy import scrape_jobs
            except ImportError:
                python_available = False
            
            return {
                'go_workers': {
                    'enabled': self.go_worker_enabled,
                    'supported_sites': list(self.go_supported_sites),
                    'workers': go_health,
                    'queue_status': queue_status
                },
                'python_jobspy': {
                    'available': python_available,
                    'supported_sites': list(self.python_supported_sites),
                    'fallback_enabled': self.fallback_to_python
                },
                'routing': {
                    'worker_timeout': self.worker_timeout,
                    'cache_enabled': settings.ENABLE_CACHE
                },
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting scraper status: {e}")
            return {'error': str(e)}


# Global hybrid service instance
hybrid_job_service = HybridJobService()