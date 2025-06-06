"""Background job processing for JobSpy Docker API."""
import asyncio
from typing import Dict, Any, Optional
import uuid
import logging
from datetime import datetime

from jobspy import scrape_jobs
from app.models.admin_models import SearchStatus

logger = logging.getLogger(__name__)

# Simple in-memory job storage (would use a database in production)
jobs = {}

class BackgroundService:
    def __init__(self):
        self.running_searches = set()

    async def execute_search(self, search_id: str, search_params: Dict[str, Any]):
        """Execute a job search in the background"""
        if search_id in self.running_searches:
            logger.warning(f"Search {search_id} is already running")
            return

        self.running_searches.add(search_id)
        
        try:
            logger.info(f"Starting background search {search_id}")
            
            # Update job status
            if search_id not in jobs:
                jobs[search_id] = {
                    "id": search_id,
                    "status": "running",
                    "created_at": datetime.now().isoformat(),
                    "params": search_params,
                }
            else:
                jobs[search_id]["status"] = "running"
                jobs[search_id]["started_at"] = datetime.now().isoformat()
            
            # Prepare JobSpy parameters
            jobspy_params = {
                'site_name': search_params.get('site_names', ['indeed']),
                'search_term': search_params.get('search_term'),
                'location': search_params.get('location'),
                'country_indeed': search_params.get('country_indeed', 'USA'),
                'results_wanted': search_params.get('results_wanted', 50),
                'job_type': search_params.get('job_type'),
                'is_remote': search_params.get('is_remote'),
                'distance': search_params.get('distance', 50),
                'description_format': 'markdown',
                'verbose': 1  # Reduce verbosity for background tasks
            }
            
            # Remove None values
            jobspy_params = {k: v for k, v in jobspy_params.items() if v is not None}
            
            logger.info(f"Executing search with parameters: {jobspy_params}")
            
            # Execute the search (run in thread pool to avoid blocking)
            loop = asyncio.get_event_loop()
            jobs_df = await loop.run_in_executor(None, scrape_jobs, **jobspy_params)
            
            jobs_found = len(jobs_df) if jobs_df is not None else 0
            
            logger.info(f"Search {search_id} completed successfully. Found {jobs_found} jobs")
            
            # Update job status
            jobs[search_id].update({
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "jobs_found": jobs_found,
                "result": jobs_df.to_dict('records') if jobs_df is not None else []
            })
            
        except Exception as e:
            error_msg = f"Search failed: {str(e)}"
            logger.error(f"Search {search_id} failed: {e}", exc_info=True)
            
            # Update job status to failed
            jobs[search_id].update({
                "status": "failed",
                "completed_at": datetime.now().isoformat(),
                "error": error_msg
            })
            
        finally:
            self.running_searches.discard(search_id)

    async def get_running_searches(self):
        """Get list of currently running search IDs"""
        return list(self.running_searches)

    async def cancel_search(self, search_id: str) -> bool:
        """Cancel a running search"""
        if search_id in self.running_searches:
            self.running_searches.discard(search_id)
            if search_id in jobs:
                jobs[search_id].update({
                    "status": "cancelled",
                    "completed_at": datetime.now().isoformat()
                })
            logger.info(f"Search {search_id} cancelled")
            return True
        return False

# Global instance
background_service = BackgroundService()

async def process_job_async(job_id: str, search_function, params: Dict[str, Any]):
    """Process a job asynchronously."""
    try:
        logger.info(f"Starting background job {job_id}")
        jobs[job_id]["status"] = "running"
        
        # Execute the search
        result, is_cached = await asyncio.to_thread(search_function, params)
        
        # Store result
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = result
        jobs[job_id]["is_cached"] = is_cached
        jobs[job_id]["completed_at"] = datetime.now().isoformat()
        
        logger.info(f"Completed background job {job_id}")
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {str(e)}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)

def create_background_job(search_function, params: Dict[str, Any]) -> str:
    """Create a new background job."""
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "id": job_id,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "params": params,
    }
    
    # Start the background task
    asyncio.create_task(process_job_async(job_id, search_function, params))
    
    return job_id

def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Get the status of a job."""
    return jobs.get(job_id)
