from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
import json
import csv
import io
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.middleware.api_key_auth import get_api_key
from app.db.database import get_db
from app.models import JobSearchParams, JobResponse, PaginatedJobResponse
from app.models.tracking_models import JobPosting, Company, Location, JobCategory, ScrapingRun
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
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of results per page"),
    format: str = Query("json", description="Response format: json or csv"),
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    Search for jobs in the tracking database with advanced filtering.
    
    This endpoint searches the job tracking database and supports:
    - Full-text search on job titles and descriptions
    - Location-based filtering
    - Company and job type filters
    - Salary range filtering
    - Experience level filtering
    - Date range filtering
    - Pagination
    - CSV export
    """
    
    # Build cache key
    cache_key = f"job_search:{hash(str(sorted([
        ('search_term', search_term), ('location', location), ('job_type', job_type),
        ('company', company), ('salary_min', salary_min), ('salary_max', salary_max),
        ('experience_level', experience_level), ('is_remote', is_remote),
        ('days_old', days_old), ('page', page), ('page_size', page_size)
    ])))}"
    
    # Try cache first
    if settings.ENABLE_CACHE:
        cached_result = await cache.get(cache_key)
        if cached_result:
            if format == "csv":
                return _create_csv_response(cached_result['jobs'])
            return PaginatedJobResponse(**cached_result, cached=True)
    
    # Build query
    query = db.query(JobPosting).join(Company).outerjoin(Location).outerjoin(JobCategory)
    
    # Apply filters
    if search_term:
        search_filter = or_(
            func.lower(JobPosting.title).contains(search_term.lower()),
            func.lower(JobPosting.description).contains(search_term.lower()),
            func.lower(Company.name).contains(search_term.lower())
        )
        query = query.filter(search_filter)
    
    if location:
        location_filter = or_(
            func.lower(Location.city).contains(location.lower()),
            func.lower(Location.state).contains(location.lower()),
            func.lower(Location.country).contains(location.lower())
        )
        query = query.filter(location_filter)
    
    if company:
        query = query.filter(func.lower(Company.name).contains(company.lower()))
    
    if job_type:
        query = query.filter(func.lower(JobPosting.job_type) == job_type.lower())
    
    if experience_level:
        query = query.filter(func.lower(JobPosting.experience_level) == experience_level.lower())
    
    if is_remote is not None:
        query = query.filter(JobPosting.is_remote == is_remote)
    
    if salary_min:
        query = query.filter(
            or_(
                JobPosting.salary_min >= salary_min,
                JobPosting.salary_max >= salary_min
            )
        )
    
    if salary_max:
        query = query.filter(
            or_(
                JobPosting.salary_min <= salary_max,
                JobPosting.salary_max <= salary_max
            )
        )
    
    # Date filter
    if days_old:
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        query = query.filter(JobPosting.first_seen_at >= cutoff_date)
    
    # Only active jobs
    query = query.filter(JobPosting.status == 'active')
    
    # Get total count
    total_count = query.count()
    
    # Apply pagination
    offset = (page - 1) * page_size
    jobs = query.order_by(JobPosting.first_seen_at.desc()).offset(offset).limit(page_size).all()
    
    # Convert to response format
    jobs_data = []
    for job in jobs:
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
            'date_posted': job.first_seen_at.isoformat(),
            'job_hash': job.job_hash,
            'status': job.status,
            'job_category': job.job_category.name if job.job_category else None,
            'sources': [
                {
                    'site': source.source_site,
                    'url': source.job_url,
                    'external_id': source.external_job_id,
                    'apply_url': source.apply_url,
                    'easy_apply': source.easy_apply
                }
                for source in job.job_sources
            ],
            'metrics': {
                'total_seen_count': job.job_metrics.total_seen_count if job.job_metrics else 1,
                'sites_posted_count': job.job_metrics.sites_posted_count if job.job_metrics else 1,
                'days_active': job.job_metrics.days_active if job.job_metrics else 0
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
    query = db.query(Company).join(JobPosting)
    
    if search:
        query = query.filter(func.lower(Company.name).contains(search.lower()))
    
    if industry:
        query = query.filter(func.lower(Company.industry).contains(industry.lower()))
    
    companies = query.group_by(Company.id).order_by(
        func.count(JobPosting.id).desc()
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
    query = db.query(Location).join(JobPosting)
    
    if search:
        search_filter = or_(
            func.lower(Location.city).contains(search.lower()),
            func.lower(Location.state).contains(search.lower())
        )
        query = query.filter(search_filter)
    
    if country:
        query = query.filter(func.lower(Location.country) == country.lower())
    
    locations = query.group_by(Location.id).order_by(
        func.count(JobPosting.id).desc()
    ).limit(limit).all()
    
    return [
        {
            'id': location.id,
            'city': location.city,
            'state': location.state,
            'country': location.country,
            'region': location.region,
            'job_count': len(location.job_postings)
        }
        for location in locations
    ]

@router.get("/scraping-runs", response_model=List[Dict[str, Any]])
async def get_scraping_runs(
    source_site: Optional[str] = Query(None, description="Filter by source site"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Number of runs to return"),
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """Get recent scraping run history."""
    query = db.query(ScrapingRun)
    
    if source_site:
        query = query.filter(ScrapingRun.source_site == source_site)
    
    if status:
        query = query.filter(ScrapingRun.status == status)
    
    runs = query.order_by(ScrapingRun.started_at.desc()).limit(limit).all()
    
    return [
        {
            'id': run.id,
            'source_site': run.source_site,
            'status': run.status,
            'jobs_found': run.jobs_found,
            'jobs_new': run.jobs_new,
            'jobs_updated': run.jobs_updated,
            'started_at': run.started_at.isoformat(),
            'completed_at': run.completed_at.isoformat() if run.completed_at else None,
            'error_message': run.error_message,
            'search_params': run.search_params
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
        'date_posted', 'job_category', 'description'
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
            'job_category': job['job_category'],
            'description': job['description'][:500] if job['description'] else ""  # Truncate for CSV
        }
        writer.writerow(csv_row)
    
    output.seek(0)
    
    return StreamingResponse(
        io.StringIO(output.getvalue()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=jobs.csv"}
    )