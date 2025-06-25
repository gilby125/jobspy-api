"""
Celery tasks for job search execution.
"""
import json
from datetime import datetime, timedelta
from celery import current_task
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.celery_app import celery_app
from app.services.job_service import JobService
from app.core.config import settings


def get_db_session():
    """Create a new database session for Celery tasks"""
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


@celery_app.task(bind=True, name="app.tasks.execute_job_search")
def execute_job_search(self, search_id: int, search_params: dict):
    """
    Execute a job search task.
    
    Args:
        search_id: Database ID of the search
        search_params: Search configuration parameters
    """
    db = get_db_session()
    
    try:
        # Update status to running
        db.execute(text("""
            UPDATE scraping_runs 
            SET status = 'running', start_time = :start_time
            WHERE id = :id
        """), {"id": search_id, "start_time": datetime.now()})
        db.commit()
        
        # Update task status
        current_task.update_state(
            state="PROGRESS",
            meta={"status": "Executing job search", "search_id": search_id}
        )
        
        # Execute the actual job search
        import asyncio
        jobs_df, _ = asyncio.run(JobService.search_jobs({
            "site_name": search_params.get("site_names", ["indeed"]),
            "search_term": search_params.get("search_term"),
            "location": search_params.get("location"),
            "results_wanted": search_params.get("results_wanted", 20),
            "country_indeed": search_params.get("country_indeed", "USA")
        }))
        
        jobs_found = len(jobs_df) if not jobs_df.empty else 0
        
        # Save jobs to database if we found any
        jobs_saved = 0
        if jobs_found > 0:
            jobs_saved = asyncio.run(JobService.save_jobs_to_database(jobs_df, search_params, db, search_id))
            print(f"Saved {jobs_saved} out of {jobs_found} jobs to database")
        
        # Update with results
        db.execute(text("""
            UPDATE scraping_runs 
            SET status = 'completed', end_time = :end_time, 
                jobs_found = :jobs_found, jobs_processed = :jobs_processed
            WHERE id = :id
        """), {
            "id": search_id,
            "end_time": datetime.now(),
            "jobs_found": jobs_found,
            "jobs_processed": jobs_found
        })
        db.commit()
        
        # Handle recurring jobs
        if search_params.get("recurring"):
            schedule_next_occurrence(search_id, search_params, db)
        
        return {
            "status": "completed",
            "search_id": search_id,
            "jobs_found": jobs_found,
            "message": f"Successfully found {jobs_found} jobs"
        }
        
    except Exception as e:
        # Mark as failed
        db.execute(text("""
            UPDATE scraping_runs 
            SET status = 'failed', end_time = :end_time, 
                error_details = :error_details
            WHERE id = :id
        """), {
            "id": search_id,
            "end_time": datetime.now(),
            "error_details": json.dumps({"error": str(e)})
        })
        db.commit()
        
        # Update task status
        current_task.update_state(
            state="FAILURE",
            meta={"status": "Failed", "error": str(e), "search_id": search_id}
        )
        
        raise e
        
    finally:
        db.close()


def schedule_next_occurrence(search_id: int, search_params: dict, db):
    """Schedule the next occurrence of a recurring search"""
    from datetime import timedelta
    
    try:
        interval = search_params.get("recurring_interval", "daily")
        
        # Calculate next run time
        if interval == "daily":
            next_time = datetime.now() + timedelta(days=1)
        elif interval == "weekly":
            next_time = datetime.now() + timedelta(weeks=1)
        elif interval == "monthly":
            next_time = datetime.now() + timedelta(days=30)
        else:
            return
        
        # Create new scheduled search
        result = db.execute(text("""
            INSERT INTO scraping_runs (source_platform, search_terms, locations, 
                                     start_time, status, jobs_found, jobs_processed, 
                                     jobs_skipped, error_count, config_used)
            VALUES (:source_platform, ARRAY[:search_term], ARRAY[:location], :start_time, 
                    :status, :jobs_found, :jobs_processed, :jobs_skipped, 
                    :error_count, :config_used)
            RETURNING id
        """), {
            "source_platform": ",".join(search_params.get("site_names", ["indeed"])),
            "search_term": search_params.get("search_term", ""),
            "location": search_params.get("location", ""),
            "start_time": next_time,
            "status": "pending",
            "jobs_found": 0,
            "jobs_processed": 0,
            "jobs_skipped": 0,
            "error_count": 0,
            "config_used": json.dumps(search_params)
        })
        
        new_search_id = result.fetchone()[0]
        db.commit()
        
        # Schedule the next execution
        execute_job_search.apply_async(
            args=[new_search_id, search_params],
            eta=next_time
        )
        
    except Exception as e:
        print(f"Error scheduling next occurrence: {e}")


@celery_app.task(name="app.tasks.cleanup_old_results")
def cleanup_old_results():
    """Clean up old job search results (run periodically)"""
    db = get_db_session()
    
    try:
        # Delete results older than 30 days
        cutoff_date = datetime.now() - timedelta(days=30)
        
        result = db.execute(text("""
            DELETE FROM scraping_runs 
            WHERE created_at < :cutoff_date AND status IN ('completed', 'failed')
        """), {"cutoff_date": cutoff_date})
        
        deleted_count = result.rowcount
        db.commit()
        
        return {"deleted_count": deleted_count, "cutoff_date": cutoff_date.isoformat()}
        
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.check_pending_recurring_searches")
def check_pending_recurring_searches(self):
    """
    Periodic task to check for pending recurring searches that need to be executed.
    Runs every minute via Celery Beat.
    """
    
    try:
        db = get_db_session()
        
        # Find pending searches that are due for execution
        now = datetime.utcnow()
        
        result = db.execute(text("""
            SELECT id, config_used, start_time, created_at
            FROM scraping_runs 
            WHERE status = 'pending' 
            AND start_time <= :now
            AND celery_task_id IS NULL
            ORDER BY start_time ASC
            LIMIT 50
        """), {"now": now})
        
        pending_searches = result.fetchall()
        scheduled_count = 0
        
        for search in pending_searches:
            try:
                search_id = search[0]
                config = search[1] if isinstance(search[1], dict) else json.loads(search[1])
                
                # Schedule the search execution
                task = execute_job_search.apply_async(
                    args=[search_id, config],
                    countdown=5  # Small delay to avoid immediate execution
                )
                
                # Update the database record with the Celery task ID
                db.execute(text("""
                    UPDATE scraping_runs 
                    SET celery_task_id = :task_id, status = 'scheduled'
                    WHERE id = :search_id
                """), {
                    "task_id": task.id,
                    "search_id": search_id
                })
                
                scheduled_count += 1
                
            except Exception as e:
                print(f"Error scheduling search {search[0]}: {e}")
                continue
        
        db.commit()
        
        return {
            "scheduled_count": scheduled_count,
            "total_pending": len(pending_searches),
            "timestamp": now.isoformat()
        }
        
    except Exception as e:
        db.rollback()
        print(f"Error in check_pending_recurring_searches: {e}")
        raise e
    finally:
        db.close()