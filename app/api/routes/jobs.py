from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
import csv
import io
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func

from app.api.deps import get_api_key
from app.db.database import get_db
from app.pydantic_models import PaginatedJobResponse
from app.models.existing_models import ExistingJobPosting, ExistingCompany, ExistingLocation, ExistingJobCategory
from app.services.job_tracking_service import job_tracking_service
from app.cache import cache
from app.core.config import settings

router = APIRouter()

@router.get("/search_jobs", response_model=PaginatedJobResponse)
async def search_jobs(
    background_tasks: BackgroundTasks,
    search_term: Optional[str] = Query(None, description="Job search term"),
    location: Optional[str] = Query(None, description="Job location"),
    job_type: Optional[str] = Query(None, description="Job type filter"),
    company: Optional[str] = Query(None, description="Company name filter"),
    salary_min: Optional[int] = Query(None, description="Minimum salary filter"),
    salary_max: Optional[int] = Query(None, description="Maximum salary filter"),
    experience_level: Optional[str] = Query(None, description="Experience level filter"),
    is_remote: Optional[bool] = Query(None, description="Remote job filter"),
    days_old: Optional[int] = Query(30, description="Maximum days since posting"),
    sort_by: str = Query("first_seen_date", description="Sort field: first_seen_date, date_posted, title, company, salary_min, salary_max"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of results per page"),
    format: str = Query("json", description="Response format: json or csv"),
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    Search for jobs in the tracking database with advanced filtering and sorting.
    
    This endpoint searches the job tracking database and supports:
    - Full-text search on job titles and descriptions
    - Location-based filtering
    - Company and job type filters
    - Salary range filtering
    - Experience level filtering
    - Date range filtering
    - Sorting by multiple fields (first_seen_date, date_posted, title, company, salary)
    - Pagination
    - CSV export
    """
    
    # Validate sort parameters
    valid_sort_fields = {
        'first_seen_date': ExistingJobPosting.date_scraped,
        'date_posted': ExistingJobPosting.date_posted,
        'title': ExistingJobPosting.title,
        'company': ExistingCompany.name,
        'salary_min': ExistingJobPosting.salary_min,
        'salary_max': ExistingJobPosting.salary_max
    }
    
    if sort_by not in valid_sort_fields:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid sort_by field. Valid options: {', '.join(valid_sort_fields.keys())}"
        )
    
    if sort_order not in ['asc', 'desc']:
        raise HTTPException(
            status_code=400,
            detail="Invalid sort_order. Valid options: asc, desc"
        )
    
    # Build cache key
    cache_key = f"job_search:{hash(str(sorted([
        ('search_term', search_term), ('location', location), ('job_type', job_type),
        ('company', company), ('salary_min', salary_min), ('salary_max', salary_max),
        ('experience_level', experience_level), ('is_remote', is_remote),
        ('days_old', days_old), ('sort_by', sort_by), ('sort_order', sort_order),
        ('page', page), ('page_size', page_size)
    ])))}"
    
    # Try cache first
    if settings.ENABLE_CACHE:
        cached_result = await cache.get(cache_key)
        if cached_result:
            if format == "csv":
                return _create_csv_response(cached_result['jobs'])
            return PaginatedJobResponse(**cached_result, cached=True)
    
    # Build query with eager loading to prevent N+1 queries
    query = db.query(ExistingJobPosting).join(ExistingCompany).outerjoin(ExistingLocation).outerjoin(ExistingJobCategory).options(
        joinedload(ExistingJobPosting.company),
        joinedload(ExistingJobPosting.location),
        joinedload(ExistingJobPosting.job_category),
        joinedload(ExistingJobPosting.job_metrics)
    )
    
    # Apply filters
    if search_term:
        search_filter = or_(
            func.lower(ExistingJobPosting.title).contains(search_term.lower()),
            func.lower(ExistingJobPosting.description).contains(search_term.lower()),
            func.lower(ExistingCompany.name).contains(search_term.lower())
        )
        query = query.filter(search_filter)
    
    if location:
        location_filter = or_(
            func.lower(ExistingLocation.city).contains(location.lower()),
            func.lower(ExistingLocation.state).contains(location.lower()),
            func.lower(ExistingLocation.country).contains(location.lower())
        )
        query = query.filter(location_filter)
    
    if company:
        query = query.filter(func.lower(ExistingCompany.name).contains(company.lower()))
    
    if job_type:
        query = query.filter(func.lower(ExistingJobPosting.job_type) == job_type.lower())
    
    if experience_level:
        query = query.filter(func.lower(ExistingJobPosting.experience_level) == experience_level.lower())
    
    if is_remote is not None:
        query = query.filter(ExistingJobPosting.is_remote == is_remote)
    
    if salary_min:
        query = query.filter(
            or_(
                ExistingJobPosting.salary_min >= salary_min,
                ExistingJobPosting.salary_max >= salary_min
            )
        )
    
    if salary_max:
        query = query.filter(
            or_(
                ExistingJobPosting.salary_min <= salary_max,
                ExistingJobPosting.salary_max <= salary_max
            )
        )
    
    # Date filter - use date_scraped as the first seen date
    if days_old:
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        query = query.filter(ExistingJobPosting.date_scraped >= cutoff_date)
    
    # Only active jobs
    query = query.filter(ExistingJobPosting.is_active)
    
    # Get total count
    total_count = query.count()
    
    # Apply sorting
    sort_field = valid_sort_fields[sort_by]
    if sort_order == 'desc':
        query = query.order_by(sort_field.desc())
    else:
        query = query.order_by(sort_field.asc())
    
    # Apply pagination
    offset = (page - 1) * page_size
    jobs = query.offset(offset).limit(page_size).all()
    
    # Convert to response format
    jobs_data = []
    for job in jobs:
        # Calculate repost count dynamically by finding similar jobs 
        # (same title and company but different external_id)
        repost_count = 0
        if job.title and job.company:
            repost_count = db.query(ExistingJobPosting).filter(
                ExistingJobPosting.title == job.title,
                ExistingJobPosting.company_id == job.company_id,
                ExistingJobPosting.external_id != job.external_id,
                ExistingJobPosting.is_active
            ).count()
        
        # Calculate days active
        if job.date_scraped and job.last_seen:
            days_active = (job.last_seen.date() - job.date_scraped.date()).days
        else:
            days_active = 0
        
        job_dict = {
            'id': job.id,
            'title': job.title,
            'company': job.company.name,
            'company_url': job.company.domain,
            'location': f"{job.location.city}, {job.location.state}, {job.location.country}" if job.location else "Remote",
            'job_type': job.job_type,
            'experience_level': job.experience_level,
            'is_remote': job.is_remote,
            'description': job.description,
            'requirements': job.requirements,
            'min_amount': float(job.salary_min) if job.salary_min else None,
            'max_amount': float(job.salary_max) if job.salary_max else None,
            'currency': job.salary_currency,
            'interval': job.salary_interval,
            'date_posted': job.date_posted.isoformat() if job.date_posted else None,  # Original posting date
            'first_seen_date': job.date_scraped.isoformat(),  # When we first discovered it
            'external_id': job.external_id,
            'source_platform': job.source_platform,
            'job_url': job.job_url,
            'application_url': job.application_url,
            'easy_apply': job.easy_apply,
            'status': 'active' if job.is_active else 'inactive',
            'job_category': job.job_category.name if job.job_category else None,
            'skills': job.skills,
            'metadata': job.job_metadata,
            'metrics': {
                'view_count': job.job_metrics.view_count if job.job_metrics else 0,
                'application_count': job.job_metrics.application_count if job.job_metrics else 0,
                'save_count': job.job_metrics.save_count if job.job_metrics else 0,
                'search_appearance_count': job.job_metrics.search_appearance_count if job.job_metrics else 0,
                'days_active': days_active,
                'repost_count': repost_count
            }
        }
        jobs_data.append(job_dict)
    
    # Calculate pagination info
    total_pages = (total_count + page_size - 1) // page_size
    
    result = {
        'count': total_count,
        'total_pages': total_pages,
        'current_page': page,
        'page_size': page_size,
        'jobs': jobs_data,
        'cached': False,
        'next_page': f"/api/v1/search_jobs?page={page + 1}" if page < total_pages else None,
        'previous_page': f"/api/v1/search_jobs?page={page - 1}" if page > 1 else None
    }
    
    # Cache the result
    if settings.ENABLE_CACHE:
        await cache.set(cache_key, result, expire=settings.CACHE_EXPIRY)
    
    # Return CSV if requested
    if format == "csv":
        return _create_csv_response(jobs_data)
    
    return PaginatedJobResponse(**result)

@router.get("/analytics", response_model=Dict[str, Any])
async def get_job_analytics(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    location_id: Optional[int] = Query(None, description="Filter by location ID"),
    days_back: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    Get job market analytics and trends.
    
    Returns comprehensive analytics including:
    - Total job counts and trends
    - Top hiring companies
    - Job type distribution
    - Salary trends and statistics
    - Geographic distribution
    """
    analytics = job_tracking_service.get_job_analytics(
        db=db,
        company_id=company_id,
        location_id=location_id,
        days_back=days_back
    )
    
    return analytics

@router.get("/companies", response_model=List[Dict[str, Any]])
async def get_companies(
    search: Optional[str] = Query(None, description="Search company names"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    limit: int = Query(50, ge=1, le=500, description="Number of companies to return"),
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """Get list of companies with job postings."""
    query = db.query(ExistingCompany).join(ExistingJobPosting)
    
    if search:
        query = query.filter(func.lower(ExistingCompany.name).contains(search.lower()))
    
    if industry:
        query = query.filter(func.lower(ExistingCompany.industry).contains(industry.lower()))
    
    companies = query.group_by(ExistingCompany.id).order_by(
        func.count(ExistingJobPosting.id).desc()
    ).limit(limit).all()
    
    return [
        {
            'id': company.id,
            'name': company.name,
            'domain': company.domain,
            'industry': company.industry,
            'company_size': company.company_size,
            'headquarters_location': company.headquarters_location,
            'description': company.description,
            'logo_url': company.logo_url,
            'job_count': len(company.job_postings)
        }
        for company in companies
    ]

@router.get("/locations", response_model=List[Dict[str, Any]])
async def get_locations(
    search: Optional[str] = Query(None, description="Search location names"),
    country: Optional[str] = Query(None, description="Filter by country"),
    limit: int = Query(100, ge=1, le=500, description="Number of locations to return"),
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """Get list of job locations."""
    query = db.query(ExistingLocation).join(ExistingJobPosting)
    
    if search:
        search_filter = or_(
            func.lower(ExistingLocation.city).contains(search.lower()),
            func.lower(ExistingLocation.state).contains(search.lower())
        )
        query = query.filter(search_filter)
    
    if country:
        query = query.filter(func.lower(ExistingLocation.country) == country.lower())
    
    locations = query.group_by(ExistingLocation.id).order_by(
        func.count(ExistingJobPosting.id).desc()
    ).limit(limit).all()
    
    return [
        {
            'id': location.id,
            'city': location.city,
            'state': location.state,
            'country': location.country,
            'latitude': float(location.latitude) if location.latitude else None,
            'longitude': float(location.longitude) if location.longitude else None,
            'metro_area': location.metro_area,
            'timezone': location.timezone,
            'job_count': len(location.job_postings)
        }
        for location in locations
    ]

@router.get("/scraping-runs", response_model=List[Dict[str, Any]])
async def get_scraping_runs(
    source_platform: Optional[str] = Query(None, description="Filter by source platform"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Number of runs to return"),
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """Get recent scraping run history."""
    from sqlalchemy import text
    
    # Build WHERE clause
    where_conditions = []
    params = {"limit": limit}
    
    if source_platform:
        where_conditions.append("source_platform = :source_platform")
        params["source_platform"] = source_platform
    
    if status:
        where_conditions.append("status = :status")
        params["status"] = status
    
    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
    
    runs_sql = f"""
        SELECT 
            id, source_platform, status, jobs_found, jobs_processed, jobs_skipped,
            start_time, end_time, error_details, config_used
        FROM scraping_runs 
        WHERE {where_clause}
        ORDER BY start_time DESC 
        LIMIT :limit
    """
    
    runs = db.execute(text(runs_sql), params).fetchall()
    
    return [
        {
            'id': run[0],
            'source_platform': run[1],
            'status': run[2],
            'jobs_found': run[3],
            'jobs_processed': run[4],
            'jobs_skipped': run[5],
            'start_time': run[6].isoformat() if run[6] else None,
            'end_time': run[7].isoformat() if run[7] else None,
            'error_details': run[8],
            'config_used': run[9]
        }
        for run in runs
    ]

def _create_csv_response(jobs_data: List[Dict[str, Any]]) -> StreamingResponse:
    """Create CSV response from jobs data."""
    output = io.StringIO()
    
    if not jobs_data:
        return StreamingResponse(
            io.StringIO("No jobs found").read(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=jobs.csv"}
        )
    
    # CSV headers
    fieldnames = [
        'title', 'company', 'location', 'job_type', 'experience_level',
        'is_remote', 'min_amount', 'max_amount', 'currency', 'interval',
        'date_posted', 'first_seen_date', 'job_category', 'repost_count', 'description'
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for job in jobs_data:
        # Flatten job data for CSV
        csv_row = {
            'title': job['title'],
            'company': job['company'],
            'location': job['location'],
            'job_type': job['job_type'],
            'experience_level': job['experience_level'],
            'is_remote': job['is_remote'],
            'min_amount': job['min_amount'],
            'max_amount': job['max_amount'],
            'currency': job['currency'],
            'interval': job['interval'],
            'date_posted': job['date_posted'],
            'first_seen_date': job['first_seen_date'],
            'job_category': job['job_category'],
            'repost_count': job['metrics']['repost_count'],
            'description': job['description'][:500] if job['description'] else ""  # Truncate for CSV
        }
        writer.writerow(csv_row)
    
    output.seek(0)
    
    return StreamingResponse(
        io.StringIO(output.getvalue()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=jobs.csv"}
    )