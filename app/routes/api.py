from fastapi import APIRouter, Depends, Query, HTTPException, Request
from typing import List, Optional, Union
import logging
import time
import uuid
import traceback

from app.pydantic_models import JobSearchParams, JobResponse, PaginatedJobResponse
from app.core.config import settings
from app.api.deps import get_api_key
from app.services.job_service import JobService
from sqlalchemy import text
from datetime import datetime
import json
from app.db.database import get_db
from app.utils.validation_helpers import VALID_PARAMETERS, get_parameter_suggestion, generate_error_suggestions
from sqlalchemy.orm import Session
from app.routes.api_helpers import parse_date_posted

router = APIRouter()
logger = logging.getLogger(__name__)

SUPPORTED_COUNTRIES_INDEED = {
    "Argentina", "Australia", "Austria", "Bahrain", "Belgium", "Brazil", "Canada", "Chile", "China", "Colombia",
    "Costa Rica", "Czech Republic", "Denmark", "Ecuador", "Egypt", "Finland", "France", "Germany", "Greece",
    "Hong Kong", "Hungary", "India", "Indonesia", "Ireland", "Israel", "Italy", "Japan", "Kuwait", "Luxembourg",
    "Malaysia", "Mexico", "Morocco", "Netherlands", "New Zealand", "Nigeria", "Norway", "Oman", "Pakistan",
    "Panama", "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Saudi Arabia", "Singapore",
    "South Africa", "South Korea", "Spain", "Sweden", "Switzerland", "Taiwan", "Thailand", "Turkey", "Ukraine",
    "United Arab Emirates", "UK", "USA", "Uruguay", "Venezuela", "Vietnam"
}

def validate_job_search_params(
    site_name,
    country_indeed,
    hours_old,
    job_type,
    is_remote,
    easy_apply,
    description_format=None,
    verbose=None,
    page=None,
    page_size=None,
    paginate=None,
    endpoint="search_jobs"
):
    # Normalize site names
    snames = [s.lower() for s in site_name] if site_name else []
    # Supported country validation for Indeed/Glassdoor
    if ("indeed" in snames or "glassdoor" in snames):
        if not country_indeed:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Missing required parameter",
                    "parameter": "country_indeed",
                    "message": "country_indeed is required when searching Indeed or Glassdoor.",
                    "suggestion": "Specify a supported country using the country_indeed parameter. See documentation for valid values."
                }
            )
        if country_indeed not in SUPPORTED_COUNTRIES_INDEED:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid country_indeed value",
                    "invalid_value": country_indeed,
                    "valid_countries": sorted(SUPPORTED_COUNTRIES_INDEED),
                    "suggestion": "Use one of the supported country names exactly as listed in the documentation."
                }
            )
    # Parameter conflict logic for Indeed
    if "indeed" in snames:
        conflict_params = []
        if hours_old is not None:
            if (job_type is not None or is_remote is not None) or (easy_apply is not None):
                conflict_params = ["hours_old", "job_type/is_remote", "easy_apply"]
        elif (job_type is not None or is_remote is not None) and easy_apply is not None:
            conflict_params = ["job_type/is_remote", "easy_apply"]
        if conflict_params:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Parameter conflict for Indeed",
                    "conflicting_parameters": conflict_params,
                    "message": (
                        "Indeed searches only support one of the following at a time: "
                        "hours_old, (job_type & is_remote), or easy_apply."
                    ),
                    "suggestion": (
                        "Remove one or more of these parameters so that only one group is used per search. "
                        "See documentation for details."
                    )
                }
            )
    # Parameter conflict logic for LinkedIn
    if "linkedin" in snames:
        if hours_old is not None and easy_apply is not None:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Parameter conflict for LinkedIn",
                    "conflicting_parameters": ["hours_old", "easy_apply"],
                    "message": (
                        "LinkedIn searches only support one of the following at a time: hours_old or easy_apply."
                    ),
                    "suggestion": (
                        "Remove either hours_old or easy_apply from your search parameters."
                    )
                }
            )

    # --- General parameter validation ---
    errors = []
    # site_name
    if site_name:
        for s in site_name:
            if s not in VALID_PARAMETERS["site_name"]:
                errors.append(get_parameter_suggestion("site_name", s))
    # job_type
    if job_type and job_type not in VALID_PARAMETERS["job_type"]:
        errors.append(get_parameter_suggestion("job_type", job_type))
    # description_format
    if description_format and description_format not in VALID_PARAMETERS["description_format"]:
        errors.append(get_parameter_suggestion("description_format", description_format))
    # verbose
    if verbose is not None and verbose not in VALID_PARAMETERS["verbose"]:
        errors.append(get_parameter_suggestion("verbose", verbose))
    # page_size
    if page_size is not None and (page_size < 1 or page_size > 100):
        errors.append(get_parameter_suggestion("page_size", page_size))
    # paginate
    if paginate is not None and paginate not in [True, False, 0, 1]:
        errors.append(get_parameter_suggestion("paginate", paginate))
    # page
    if page is not None and page < 1:
        errors.append(get_parameter_suggestion("page", page))
    # If any errors, raise with all suggestions
    if errors:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid parameter(s)",
                "suggestions": errors,
            }
        )

@router.get("/search_jobs", response_model=Union[JobResponse, PaginatedJobResponse], dependencies=[Depends(get_api_key)])
async def search_jobs(
    request: Request,
    db: Session = Depends(get_db),
    # Pagination parameters
    paginate: bool = Query(False, description="Enable pagination"),
    page: int = Query(1, ge=1, description="Page number (if pagination enabled)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page (if pagination enabled)"),
    
    # Basic search parameters
    site_name: List[str] = Query(default=None, description="Job sites to search on"),
    search_term: str = Query(None, description="Job search term"),
    google_search_term: Optional[str] = Query(None, description="Search term for Google jobs"),
    location: str = Query(None, description="Job location"),
    distance: int = Query(None, description="Distance in miles"),
    
    # Job filters
    job_type: Optional[str] = Query(None, description="Job type (fulltime, parttime, internship, contract)"),
    is_remote: Optional[bool] = Query(None, description="Remote job filter"),
    hours_old: Optional[int] = Query(None, description="Filter by hours since posting"),
    easy_apply: Optional[bool] = Query(None, description="Filter for easy apply jobs"),
    
    # Advanced parameters
    results_wanted: int = Query(None, description="Number of results per site"),
    description_format: str = Query(None, description="Format of job description"),
    offset: int = Query(None, description="Offset for pagination"),
    verbose: int = Query(None, description="Controls verbosity (0: errors only, 1: errors+warnings, 2: all logs)"),
    linkedin_fetch_description: bool = Query(None, description="Fetch full LinkedIn descriptions"),
    linkedin_company_ids: Optional[List[int]] = Query(None, description="LinkedIn company IDs to filter by"),
    country_indeed: Optional[str] = Query(None, description="Country filter for Indeed & Glassdoor"),
    enforce_annual_salary: bool = Query(None, description="Convert wages to annual salary"),
):
    """
    Search for jobs across multiple platforms with optional pagination.
    
    If paginate=True, returns paginated results with next/previous page links.
    Otherwise, returns all results in a single response.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    validate_job_search_params(
        site_name=site_name,
        country_indeed=country_indeed,
        hours_old=hours_old,
        job_type=job_type,
        is_remote=is_remote,
        easy_apply=easy_apply,
        description_format=description_format,
        verbose=verbose,
        page=page,
        page_size=page_size,
        paginate=paginate,
    )
    
    # Validate site_name values
    if site_name:
        invalid_sites = [site for site in site_name if site not in VALID_PARAMETERS["site_name"]]
        if invalid_sites:
            suggestions = [get_parameter_suggestion("site_name", site) for site in invalid_sites]
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": "Invalid job site name(s)",
                    "invalid_values": invalid_sites,
                    "valid_sites": VALID_PARAMETERS["site_name"],
                    "suggestions": suggestions
                }
            )
    
    # Validate job_type
    if job_type and job_type not in VALID_PARAMETERS["job_type"]:
        suggestion = get_parameter_suggestion("job_type", job_type)
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "Invalid job type",
                "invalid_value": job_type,
                "valid_types": VALID_PARAMETERS["job_type"],
                "suggestion": suggestion
            }
        )
    
    # Validate description_format
    if description_format and description_format not in VALID_PARAMETERS["description_format"]:
        suggestion = get_parameter_suggestion("description_format", description_format)
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "Invalid description format",
                "invalid_value": description_format,
                "valid_formats": VALID_PARAMETERS["description_format"],
                "suggestion": suggestion
            }
        )
    
    # Create parameters object with all search parameters
    params = JobSearchParams(
        site_name=site_name if site_name else settings.default_site_names_list,
        search_term=search_term,
        google_search_term=google_search_term,
        location=location,
        distance=distance if distance is not None else settings.DEFAULT_DISTANCE,
        job_type=job_type,
        proxies=settings.default_proxies_list if settings.default_proxies_list else None,
        is_remote=is_remote,
        results_wanted=results_wanted if results_wanted is not None else settings.DEFAULT_RESULTS_WANTED,
        hours_old=hours_old,
        easy_apply=easy_apply,
        description_format=description_format if description_format else settings.DEFAULT_DESCRIPTION_FORMAT,
        offset=offset if offset is not None else 0,
        verbose=verbose if verbose is not None else 2,
        linkedin_fetch_description=linkedin_fetch_description if linkedin_fetch_description is not None else False,
        linkedin_company_ids=linkedin_company_ids,
        country_indeed=country_indeed if country_indeed else settings.DEFAULT_COUNTRY_INDEED,
        enforce_annual_salary=enforce_annual_salary if enforce_annual_salary is not None else False,
        ca_cert=settings.CA_CERT_PATH,
    )
    
    logger.info(f"Request {request_id}: Starting job search with parameters: {params.dict(exclude_none=True)}")
    
    try:
        # Execute the search
        jobs_df, is_cached = await JobService.search_jobs(params.dict(exclude_none=True))
        
        # Save jobs to database if we got results and it's not cached
        if not jobs_df.empty and not is_cached:
            try:
                # Create a simple scraping run record for tracking
                search_terms_array = f"ARRAY['{params.search_term}']" if params.search_term else "ARRAY[]::varchar[]"
                locations_array = f"ARRAY['{params.location}']" if params.location else "ARRAY[]::varchar[]"
                
                result = db.execute(text(f"""
                    INSERT INTO scraping_runs (source_platform, search_terms, locations, start_time, 
                                             status, jobs_found, jobs_processed, jobs_skipped, 
                                             error_count, config_used)
                    VALUES (:source_platform, {search_terms_array}, {locations_array}, :start_time, 
                            :status, :jobs_found, :jobs_processed, :jobs_skipped, 
                            :error_count, :config_used)
                    RETURNING id
                """), {
                    "source_platform": ",".join(params.site_name),
                    "start_time": datetime.now(),
                    "status": "completed",
                    "jobs_found": len(jobs_df),
                    "jobs_processed": 0,  # We'll update this as we insert jobs
                    "jobs_skipped": 0,
                    "error_count": 0,
                    "config_used": json.dumps(params.dict(exclude_none=True))
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
                logger.info(f"Saved {jobs_inserted} jobs from {','.join(params.site_name)} to database")
                        
            except Exception as e:
                logger.error(f"Error saving jobs to database: {e}")
                db.rollback()
                # Continue with the response even if database save fails
        
        # Return results - either paginated or all at once
        if paginate:
            # Calculate pagination
            total_items = len(jobs_df)
            total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
            
            # Validate page number
            if page > total_pages and total_pages > 0:
                raise HTTPException(
                    status_code=404, 
                    detail={
                        "error": f"Page {page} not found",
                        "total_pages": total_pages,
                        "suggestion": f"Use a page number between 1 and {total_pages}"
                    }
                )
            
            # Apply pagination
            start_idx = (page - 1) * page_size
            end_idx = min(start_idx + page_size, total_items)
            paginated_df = jobs_df.iloc[start_idx:end_idx] if total_items > 0 else jobs_df
            
            # Generate next/previous page URLs
            base_url = str(request.url).split("?")[0]
            query_params = dict(request.query_params)
            
            next_page = None
            if page < total_pages:
                query_params["page"] = str(page + 1)
                next_page = f"{base_url}?{'&'.join([f'{k}={v}' for k, v in query_params.items()])}"
            
            previous_page = None
            if page > 1:
                query_params["page"] = str(page - 1)
                previous_page = f"{base_url}?{'&'.join([f'{k}={v}' for k, v in query_params.items()])}"
            
            # Convert DataFrame to dictionary format
            jobs_list = paginated_df.to_dict('records') if not paginated_df.empty else []
            
            end_time = time.time()
            logger.info(f"Request {request_id}: Completed in {end_time - start_time:.2f} seconds. Found {total_items} jobs, returning page {page}/{total_pages}")
            
            return {
                "count": total_items,
                "total_pages": total_pages,
                "current_page": page,
                "page_size": page_size,
                "jobs": jobs_list,
                "cached": is_cached,
                "next_page": next_page,
                "previous_page": previous_page
            }
        else:
            # Return all results without pagination
            jobs_list = jobs_df.to_dict('records') if not jobs_df.empty else []
            
            end_time = time.time()
            logger.info(f"Request {request_id}: Completed in {end_time - start_time:.2f} seconds. Found {len(jobs_list)} jobs")
            
            return {
                "count": len(jobs_list),
                "jobs": jobs_list,
                "cached": is_cached
            }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        
        logger.error(f"Request {request_id}: Error scraping jobs: {str(e)}")
        logger.debug(traceback.format_exc())
        
        # Provide more helpful error details
        error_message = str(e)
        suggestion = "Try simplifying your search or using fewer job sites"
        
        if "proxy" in error_message.lower():
            suggestion = "Check your proxy configuration or try without a proxy"
        elif "timeout" in error_message.lower():
            suggestion = "The request timed out. Try reducing the number of job sites or results_wanted"
        elif "captcha" in error_message.lower():
            suggestion = "A CAPTCHA was encountered. Try using a different proxy or reduce request frequency"
        
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Error scraping jobs",
                "message": error_message,
                "suggestion": suggestion
            }
        )

@router.post("/debug/create-tables")
async def create_database_tables():
    """Debug endpoint to create database tables."""
    try:
        from app.db.database import create_tables, init_database
        init_database()
        create_tables()
        return {"status": "success", "message": "Database tables created successfully"}
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return {"status": "error", "message": f"Failed to create tables: {str(e)}"}

@router.post("/search_jobs", response_model=Union[JobResponse, PaginatedJobResponse], dependencies=[Depends(get_api_key)])
async def search_jobs_post(
    params: JobSearchParams,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Search for jobs across multiple platforms using POST method.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    validate_job_search_params(
        site_name=params.site_name if isinstance(params.site_name, list) else [params.site_name],
        country_indeed=params.country_indeed,
        hours_old=params.hours_old,
        job_type=params.job_type,
        is_remote=params.is_remote,
        easy_apply=params.easy_apply,
        description_format=params.description_format,
        verbose=params.verbose,
        page=getattr(params, "page", None),
        page_size=getattr(params, "page_size", None),
        paginate=getattr(params, "paginate", None),
    )
    
    logger.info(f"Request {request_id}: Starting job search with parameters: {params.dict(exclude_none=True)}")
    
    try:
        # Execute the search
        jobs_df, is_cached = await JobService.search_jobs(params.dict(exclude_none=True))
        
        # Save jobs to database if we got results and it's not cached
        if not jobs_df.empty and not is_cached:
            try:
                from app.services.job_tracking_service import JobTrackingService
                job_tracking_service = JobTrackingService()
                jobs_data = jobs_df.to_dict('records')
                
                # Process each site separately for better tracking
                for site_name in params.site_name:
                    site_jobs = [job for job in jobs_data if job.get('site') == site_name]
                    if site_jobs:
                        site_stats = job_tracking_service.process_scraped_jobs(
                            jobs_data=site_jobs,
                            source_site=site_name,
                            search_params=params.dict(exclude_none=True),
                            db=db
                        )
                        logger.info(f"Saved {site_stats['new_jobs']} new jobs from {site_name} to database")
                        
            except Exception as e:
                logger.error(f"Error saving jobs to database: {e}")
                # Continue with the response even if database save fails
        
        # Return all results without pagination
        jobs_list = jobs_df.to_dict('records') if not jobs_df.empty else []
        
        end_time = time.time()
        logger.info(f"Request {request_id}: Completed in {end_time - start_time:.2f} seconds. Found {len(jobs_list)} jobs")
        
        return {
            "count": len(jobs_list),
            "jobs": jobs_list,
            "cached": is_cached
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        
        logger.error(f"Request {request_id}: Error scraping jobs: {str(e)}")
        logger.debug(traceback.format_exc())
        
        # Provide more helpful error details
        error_message = str(e)
        suggestion = "Try simplifying your search or using fewer job sites"
        
        if "proxy" in error_message.lower():
            suggestion = "Check your proxy configuration or try without a proxy"
        elif "timeout" in error_message.lower():
            suggestion = "The request timed out. Try reducing the number of job sites or results_wanted"
        elif "captcha" in error_message.lower():
            suggestion = "A CAPTCHA was encountered. Try using a different proxy or reduce request frequency"
        
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Error scraping jobs",
                "message": error_message,
                "suggestion": suggestion
            }
        )

@router.post("/debug/create-tables")
async def create_database_tables():
    """Debug endpoint to create database tables."""
    try:
        from app.db.database import create_tables, init_database
        init_database()
        create_tables()
        return {"status": "success", "message": "Database tables created successfully"}
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return {"status": "error", "message": f"Failed to create tables: {str(e)}"}
