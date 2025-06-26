from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
import csv
import io
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func, and_

from app.api.deps import get_api_key
from app.db.database import get_db
from app.pydantic_models import PaginatedJobResponse
from app.models.tracking_models import JobPosting, Company, Location, JobCategory, JobSource, JobMetrics
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
    source_site: Optional[str] = Query(None, description="Filter by source site (indeed, linkedin, etc)"),
    sort_by: str = Query("first_seen_at", description="Sort field: first_seen_at, last_seen_at, title, company, salary_min, salary_max"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of results per page"),
    format: str = Query("json", description="Response format: json or csv"),
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    Search for jobs in the tracking database with advanced filtering and sorting.
    
    This endpoint searches the enhanced job tracking database and supports:
    - Full-text search on job titles and descriptions
    - Location-based filtering
    - Company and job type filters
    - Salary range filtering
    - Experience level filtering
    - Date range filtering
    - Source site filtering (filter by where job was found)
    - Sorting by multiple fields
    - Pagination
    - CSV export
    
    The tracking database includes deduplication, so each unique job appears only once
    even if it was found on multiple sites.
    """
    
    # Validate sort parameters
    valid_sort_fields = {
        'first_seen_at': JobPosting.first_seen_at,
        'last_seen_at': JobPosting.last_seen_at,
        'title': JobPosting.title,
        'company': Company.name,
        'salary_min': JobPosting.salary_min,
        'salary_max': JobPosting.salary_max
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
    cache_key = f"job_search_tracking:{hash(str(sorted([
        ('search_term', search_term), ('location', location), ('job_type', job_type),
        ('company', company), ('salary_min', salary_min), ('salary_max', salary_max),
        ('experience_level', experience_level), ('is_remote', is_remote),
        ('days_old', days_old), ('source_site', source_site),
        ('sort_by', sort_by), ('sort_order', sort_order),
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
    query = db.query(JobPosting).join(Company).outerjoin(Location).outerjoin(JobCategory).options(
        joinedload(JobPosting.company),
        joinedload(JobPosting.location),
        joinedload(JobPosting.job_category),
        joinedload(JobPosting.job_sources),
        joinedload(JobPosting.job_metrics)
    )
    
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
    
    # Source site filter
    if source_site:
        # Need to join with JobSource to filter by source
        query = query.join(JobSource).filter(
            func.lower(JobSource.source_site) == source_site.lower()
        )
    
    # Only active jobs
    query = query.filter(JobPosting.status == 'active')
    
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
        # Get all sources where this job was found
        sources = [
            {
                'site': source.source_site,
                'job_url': source.job_url,
                'external_id': source.external_job_id,
                'post_date': source.post_date.isoformat() if source.post_date else None,
                'easy_apply': source.easy_apply
            }
            for source in job.job_sources
        ]
        
        # Primary source (first found)
        primary_source = min(job.job_sources, key=lambda s: s.created_at) if job.job_sources else None
        
        job_dict = {
            'id': job.id,
            'job_hash': job.job_hash,
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
            'first_seen_at': job.first_seen_at.isoformat(),
            'last_seen_at': job.last_seen_at.isoformat(),
            'status': job.status,
            'job_category': job.job_category.name if job.job_category else None,
            'sources': sources,
            'primary_source': {
                'site': primary_source.source_site,
                'job_url': primary_source.job_url,
                'external_id': primary_source.external_job_id
            } if primary_source else None,
            'metrics': {
                'total_seen_count': job.job_metrics.total_seen_count if job.job_metrics else 0,
                'sites_posted_count': job.job_metrics.sites_posted_count if job.job_metrics else len(sources),
                'days_active': job.job_metrics.days_active if job.job_metrics else 0,
                'repost_count': job.job_metrics.repost_count if job.job_metrics else 0,
                'last_activity_date': job.job_metrics.last_activity_date.isoformat() if job.job_metrics else None
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
    
    # Count active jobs per company
    companies = db.query(
        Company,
        func.count(JobPosting.id).label('active_jobs_count')
    ).join(JobPosting).filter(
        JobPosting.status == 'active'
    )
    
    if search:
        companies = companies.filter(func.lower(Company.name).contains(search.lower()))
    
    if industry:
        companies = companies.filter(func.lower(Company.industry).contains(industry.lower()))
    
    companies = companies.group_by(Company.id).order_by(
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
            'founded_year': company.founded_year,
            'revenue_range': company.revenue_range,
            'description': company.description,
            'logo_url': company.logo_url,
            'active_jobs_count': active_jobs
        }
        for company, active_jobs in companies
    ]

@router.get("/locations", response_model=List[Dict[str, Any]])
async def get_locations(
    search: Optional[str] = Query(None, description="Search location names"),
    country: Optional[str] = Query(None, description="Filter by country"),
    limit: int = Query(50, ge=1, le=500, description="Number of locations to return"),
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """Get list of locations with job postings."""
    # Count active jobs per location
    locations = db.query(
        Location,
        func.count(JobPosting.id).label('active_jobs_count')
    ).join(JobPosting).filter(
        JobPosting.status == 'active'
    )
    
    if search:
        search_filter = or_(
            func.lower(Location.city).contains(search.lower()),
            func.lower(Location.state).contains(search.lower()),
            func.lower(Location.country).contains(search.lower())
        )
        locations = locations.filter(search_filter)
    
    if country:
        locations = locations.filter(func.lower(Location.country) == country.lower())
    
    locations = locations.group_by(Location.id).order_by(
        func.count(JobPosting.id).desc()
    ).limit(limit).all()
    
    return [
        {
            'id': location.id,
            'city': location.city,
            'state': location.state,
            'country': location.country,
            'region': location.region,
            'active_jobs_count': active_jobs
        }
        for location, active_jobs in locations
    ]

def _create_csv_response(jobs_data: List[Dict[str, Any]]) -> StreamingResponse:
    """Create a CSV response from job data."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            'id', 'title', 'company', 'location', 'job_type', 
            'min_amount', 'max_amount', 'currency', 'is_remote',
            'first_seen_at', 'last_seen_at', 'primary_source_site',
            'primary_job_url', 'sites_posted_count', 'days_active'
        ]
    )
    writer.writeheader()
    
    for job in jobs_data:
        row = {
            'id': job['id'],
            'title': job['title'],
            'company': job['company'],
            'location': job['location'],
            'job_type': job['job_type'],
            'min_amount': job['min_amount'],
            'max_amount': job['max_amount'],
            'currency': job['currency'],
            'is_remote': job['is_remote'],
            'first_seen_at': job['first_seen_at'],
            'last_seen_at': job['last_seen_at'],
            'primary_source_site': job['primary_source']['site'] if job['primary_source'] else '',
            'primary_job_url': job['primary_source']['job_url'] if job['primary_source'] else '',
            'sites_posted_count': job['metrics']['sites_posted_count'],
            'days_active': job['metrics']['days_active']
        }
        writer.writerow(row)
    
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=job_search_results.csv"}
    )