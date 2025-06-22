"""
Enhanced job tracking service that integrates with the deduplication engine.

This service handles:
1. Job scraping orchestration
2. Deduplication and database storage
3. Metrics tracking and analytics
4. Webhook notifications
"""
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.services.deduplication_service import deduplication_service
from app.models.tracking_models import (
    JobPosting, Company, Location, JobCategory, JobSource, 
    JobMetrics, ScrapingRun, WebhookSubscription
)
from app.db.database import get_db
from app.core.config import settings

logger = logging.getLogger(__name__)


class JobTrackingService:
    """Enhanced service for tracking and managing job postings."""
    
    def __init__(self):
        self.dedup_service = deduplication_service
    
    def process_scraped_jobs(
        self, 
        jobs_data: List[Dict], 
        source_site: str,
        search_params: Dict,
        db: Session
    ) -> Dict[str, Any]:
        """
        Process scraped jobs through the deduplication pipeline.
        
        Args:
            jobs_data: List of job dictionaries from scraper
            source_site: Source site name (e.g., 'indeed', 'linkedin')
            search_params: Search parameters used for scraping
            db: Database session
            
        Returns:
            Dictionary with processing statistics
        """
        stats = {
            'total_jobs': len(jobs_data),
            'new_jobs': 0,
            'duplicate_jobs': 0,
            'updated_jobs': 0,
            'errors': 0,
            'new_companies': 0,
            'processed_jobs': []
        }
        
        # Create scraping run record
        scraping_run = ScrapingRun(
            source_site=source_site,
            search_params=search_params,
            status='running',
            jobs_found=len(jobs_data),
            started_at=datetime.utcnow()
        )
        db.add(scraping_run)
        db.commit()
        
        try:
            for job_data in jobs_data:
                try:
                    result = self._process_single_job(job_data, source_site, db)
                    
                    if result['action'] == 'created':
                        stats['new_jobs'] += 1
                        if result.get('new_company'):
                            stats['new_companies'] += 1
                    elif result['action'] == 'merged':
                        stats['duplicate_jobs'] += 1
                    elif result['action'] == 'updated':
                        stats['updated_jobs'] += 1
                    
                    stats['processed_jobs'].append({
                        'job_id': result['job_posting'].id,
                        'title': result['job_posting'].title,
                        'company': result['job_posting'].company.name,
                        'action': result['action'],
                        'similarity_score': result.get('similarity_score')
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing job: {e}")
                    stats['errors'] += 1
            
            # Update scraping run
            scraping_run.status = 'completed'
            scraping_run.jobs_new = stats['new_jobs']
            scraping_run.jobs_updated = stats['updated_jobs']
            scraping_run.completed_at = datetime.utcnow()
            
        except Exception as e:
            scraping_run.status = 'failed'
            scraping_run.error_message = str(e)
            logger.error(f"Scraping run failed: {e}")
        
        db.commit()
        
        logger.info(f"Processed {stats['total_jobs']} jobs from {source_site}: "
                   f"{stats['new_jobs']} new, {stats['duplicate_jobs']} duplicates, "
                   f"{stats['updated_jobs']} updated, {stats['errors']} errors")
        
        return stats
    
    def _process_single_job(
        self, 
        job_data: Dict, 
        source_site: str, 
        db: Session
    ) -> Dict[str, Any]:
        """
        Process a single job through the deduplication pipeline.
        
        Args:
            job_data: Job data dictionary
            source_site: Source site name
            db: Database session
            
        Returns:
            Dictionary with processing result
        """
        # Check for duplicates
        is_duplicate, existing_job = self.dedup_service.is_duplicate_job(job_data, db)
        
        if is_duplicate and existing_job:
            # Merge with existing job
            updated_job = self.dedup_service.merge_job_sources(
                existing_job, job_data, source_site, db
            )
            
            return {
                'action': 'merged',
                'job_posting': updated_job,
                'similarity_score': 1.0  # Exact match
            }
        
        # Create new job posting
        job_posting = self._create_new_job_posting(job_data, source_site, db)
        
        return {
            'action': 'created',
            'job_posting': job_posting,
            'new_company': job_posting.company_id  # Will be set if company was created
        }
    
    def _create_new_job_posting(
        self, 
        job_data: Dict, 
        source_site: str, 
        db: Session
    ) -> JobPosting:
        """
        Create a new job posting with all related entities.
        
        Args:
            job_data: Job data dictionary
            source_site: Source site name
            db: Database session
            
        Returns:
            Created JobPosting instance
        """
        # Get or create company
        company = self._get_or_create_company(job_data, db)
        
        # Get or create location
        location = self._get_or_create_location(job_data, db)
        
        # Get or create job category
        job_category = self._get_or_create_job_category(job_data, db)
        
        # Generate job hash
        job_hash = self.dedup_service.generate_job_hash(job_data)
        
        # Create job posting
        job_posting = JobPosting(
            job_hash=job_hash,
            title=job_data.get('title', '').strip(),
            company_id=company.id,
            location_id=location.id if location else None,
            job_category_id=job_category.id if job_category else None,
            job_type=job_data.get('job_type', '').lower(),
            experience_level=self._extract_experience_level(job_data.get('title', '')),
            is_remote='remote' in job_data.get('location', '').lower(),
            description=job_data.get('description', ''),
            requirements=self._extract_requirements(job_data.get('description', '')),
            salary_min=self._parse_salary(job_data.get('min_amount')),
            salary_max=self._parse_salary(job_data.get('max_amount')),
            salary_currency=job_data.get('currency', 'USD'),
            salary_interval=job_data.get('interval', 'yearly'),
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
            status='active'
        )
        
        db.add(job_posting)
        db.flush()  # Get the ID
        
        # Create job source
        job_source = JobSource(
            job_posting_id=job_posting.id,
            source_site=source_site,
            external_job_id=job_data.get('job_id'),
            job_url=job_data.get('job_url', ''),
            post_date=self._parse_date(job_data.get('date_posted')),
            apply_url=job_data.get('job_url_direct'),
            easy_apply=job_data.get('easy_apply', False)
        )
        
        # Create job metrics
        job_metrics = JobMetrics(
            job_posting_id=job_posting.id,
            total_seen_count=1,
            sites_posted_count=1,
            days_active=0,
            last_activity_date=date.today()
        )
        
        db.add(job_source)
        db.add(job_metrics)
        db.commit()
        
        logger.info(f"Created new job posting: {job_posting.title} at {company.name}")
        
        return job_posting
    
    def _get_or_create_company(self, job_data: Dict, db: Session) -> Company:
        """Get existing company or create new one."""
        company_name = job_data.get('company', '').strip()
        if not company_name:
            # Create a placeholder company
            company_name = "Unknown Company"
        
        # Normalize company name for lookup
        normalized_name = self.dedup_service._normalize_company_name(company_name)
        
        # Try to find existing company
        existing_company = db.query(Company).filter(
            func.lower(Company.name).like(f'%{normalized_name}%')
        ).first()
        
        if existing_company:
            return existing_company
        
        # Create new company
        company = Company(
            name=company_name,
            description=job_data.get('company_description'),
            logo_url=job_data.get('company_logo'),
            # These could be enhanced with external data enrichment
            industry=self._extract_industry(job_data.get('description', '')),
        )
        
        db.add(company)
        db.flush()
        
        logger.info(f"Created new company: {company.name}")
        return company
    
    def _get_or_create_location(self, job_data: Dict, db: Session) -> Optional[Location]:
        """Get existing location or create new one."""
        location_str = job_data.get('location', '').strip()
        if not location_str or location_str.lower() in ['remote', 'work from home']:
            return None
        
        # Parse location components
        city, state, country = self._parse_location_components(location_str)
        
        if not country:
            return None
        
        # Try to find existing location
        existing_location = db.query(Location).filter(
            and_(
                Location.city == city,
                Location.state == state,
                Location.country == country
            )
        ).first()
        
        if existing_location:
            return existing_location
        
        # Create new location
        location = Location(
            city=city,
            state=state,
            country=country,
            region=self._get_region_for_country(country)
        )
        
        db.add(location)
        db.flush()
        
        return location
    
    def _get_or_create_job_category(self, job_data: Dict, db: Session) -> Optional[JobCategory]:
        """Get existing job category or create new one based on title."""
        title = job_data.get('title', '').strip().lower()
        if not title:
            return None
        
        # Map common job titles to categories
        category_mapping = {
            'software': 'Software Engineering',
            'developer': 'Software Engineering',
            'engineer': 'Engineering',
            'data': 'Data Science',
            'analyst': 'Data Analysis',
            'marketing': 'Marketing',
            'sales': 'Sales',
            'manager': 'Management',
            'designer': 'Design',
            'product': 'Product Management',
            'devops': 'DevOps',
            'qa': 'Quality Assurance',
            'hr': 'Human Resources',
            'finance': 'Finance',
            'accounting': 'Finance'
        }
        
        # Find matching category
        category_name = None
        for keyword, category in category_mapping.items():
            if keyword in title:
                category_name = category
                break
        
        if not category_name:
            category_name = 'Other'
        
        # Try to find existing category
        existing_category = db.query(JobCategory).filter(
            JobCategory.name == category_name
        ).first()
        
        if existing_category:
            return existing_category
        
        # Create new category
        category = JobCategory(name=category_name)
        db.add(category)
        db.flush()
        
        return category
    
    def get_job_analytics(
        self, 
        db: Session,
        company_id: Optional[int] = None,
        location_id: Optional[int] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Get job analytics and trends.
        
        Args:
            db: Database session
            company_id: Filter by company
            location_id: Filter by location
            days_back: Number of days to look back
            
        Returns:
            Analytics dictionary
        """
        # Use raw SQL to avoid ORM model mismatches
        from datetime import timedelta
        from sqlalchemy import text
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        # Build WHERE clause
        where_conditions = ["jp.date_scraped >= :cutoff_date", "jp.is_active = true"]
        params = {"cutoff_date": cutoff_date}
        
        if company_id:
            where_conditions.append("jp.company_id = :company_id")
            params["company_id"] = company_id
        
        if location_id:
            where_conditions.append("jp.location_id = :location_id")
            params["location_id"] = location_id
        
        where_clause = " AND ".join(where_conditions)
        
        # Calculate total jobs
        total_jobs_sql = f"SELECT COUNT(*) FROM job_postings jp WHERE {where_clause}"
        total_jobs = db.execute(text(total_jobs_sql), params).fetchone()[0]
        
        # Calculate active jobs (all jobs matching our criteria are already filtered for is_active=true)
        active_jobs = total_jobs
        
        # Top companies
        top_companies_sql = f"""
            SELECT c.name, COUNT(jp.id) as job_count
            FROM job_postings jp 
            JOIN companies c ON jp.company_id = c.id
            WHERE {where_clause}
            GROUP BY c.name 
            ORDER BY COUNT(jp.id) DESC 
            LIMIT 10
        """
        top_companies = db.execute(text(top_companies_sql), params).fetchall()
        
        # Job type distribution
        job_types_sql = f"""
            SELECT jp.job_type, COUNT(jp.id) as count
            FROM job_postings jp 
            WHERE {where_clause} AND jp.job_type IS NOT NULL
            GROUP BY jp.job_type
        """
        job_types = db.execute(text(job_types_sql), params).fetchall()
        
        # Salary trends
        salary_stats_sql = f"""
            SELECT 
                AVG(jp.salary_min) as avg_min_salary,
                AVG(jp.salary_max) as avg_max_salary,
                COUNT(jp.salary_min) as salary_count
            FROM job_postings jp 
            WHERE {where_clause} AND jp.salary_min IS NOT NULL
        """
        salary_stats = db.execute(text(salary_stats_sql), params).fetchone()
        
        return {
            'total_jobs': total_jobs,
            'active_jobs': active_jobs,
            'top_companies': [{'name': row[0], 'job_count': row[1]} for row in top_companies],
            'job_type_distribution': [{'type': row[0], 'count': row[1]} for row in job_types if row[0]],
            'salary_trends': {
                'avg_min_salary': float(salary_stats[0]) if salary_stats[0] else None,
                'avg_max_salary': float(salary_stats[1]) if salary_stats[1] else None,
                'salary_sample_size': salary_stats[2] if salary_stats[2] else 0
            },
            'period_days': days_back
        }
    
    # Helper methods
    def _extract_experience_level(self, title: str) -> str:
        """Extract experience level from job title."""
        title_lower = title.lower()
        if any(word in title_lower for word in ['senior', 'sr.', 'lead', 'principal']):
            return 'senior'
        elif any(word in title_lower for word in ['junior', 'jr.', 'entry', 'associate']):
            return 'entry'
        elif any(word in title_lower for word in ['manager', 'director', 'head', 'chief']):
            return 'executive'
        else:
            return 'mid'
    
    def _extract_requirements(self, description: str) -> str:
        """Extract requirements section from job description."""
        if not description:
            return ""
        
        # Look for requirements section
        requirements_indicators = [
            'requirements:', 'qualifications:', 'must have:', 
            'you will need:', 'skills required:', 'essential:'
        ]
        
        desc_lower = description.lower()
        for indicator in requirements_indicators:
            start_idx = desc_lower.find(indicator)
            if start_idx != -1:
                # Extract next 500 characters after indicator
                requirements_text = description[start_idx:start_idx + 500]
                return requirements_text.strip()
        
        return ""
    
    def _parse_salary(self, amount: Any) -> Optional[float]:
        """Parse salary amount to float."""
        if not amount:
            return None
        
        try:
            if isinstance(amount, (int, float)):
                return float(amount)
            
            # Remove currency symbols and commas
            amount_str = str(amount).replace('$', '').replace(',', '').strip()
            return float(amount_str) if amount_str else None
        except (ValueError, TypeError):
            return None
    
    def _parse_date(self, date_str: Any) -> Optional[date]:
        """Parse date string - delegate to deduplication service."""
        return self.dedup_service._parse_date(date_str)
    
    def _parse_location_components(self, location_str: str) -> Tuple[str, str, str]:
        """Parse location string into city, state, country components."""
        parts = [part.strip() for part in location_str.split(',')]
        
        city = parts[0] if len(parts) > 0 else ""
        state = parts[1] if len(parts) > 1 else ""
        country = parts[2] if len(parts) > 2 else "USA"  # Default to USA
        
        # Clean up common patterns
        if country.upper() in ['US', 'USA', 'UNITED STATES']:
            country = 'USA'
        
        return city, state, country
    
    def _get_region_for_country(self, country: str) -> str:
        """Get region for a country."""
        region_mapping = {
            'USA': 'North America',
            'CANADA': 'North America',
            'MEXICO': 'North America',
            'UK': 'Europe',
            'GERMANY': 'Europe',
            'FRANCE': 'Europe',
            'SPAIN': 'Europe',
            'ITALY': 'Europe',
            'INDIA': 'Asia',
            'CHINA': 'Asia',
            'JAPAN': 'Asia',
            'AUSTRALIA': 'Oceania'
        }
        
        return region_mapping.get(country.upper(), 'Other')
    
    def _extract_industry(self, description: str) -> Optional[str]:
        """Extract industry from job description."""
        if not description:
            return None
        
        # Simple industry detection based on keywords
        industry_keywords = {
            'Technology': ['software', 'tech', 'startup', 'saas', 'cloud', 'ai', 'machine learning'],
            'Healthcare': ['healthcare', 'medical', 'hospital', 'clinic', 'pharmaceutical'],
            'Finance': ['finance', 'banking', 'investment', 'fintech', 'trading'],
            'Education': ['education', 'university', 'school', 'teaching', 'academic'],
            'Retail': ['retail', 'ecommerce', 'store', 'shopping', 'consumer'],
            'Manufacturing': ['manufacturing', 'factory', 'production', 'automotive'],
            'Consulting': ['consulting', 'advisory', 'professional services']
        }
        
        desc_lower = description.lower()
        for industry, keywords in industry_keywords.items():
            if any(keyword in desc_lower for keyword in keywords):
                return industry
        
        return None


# Global service instance
job_tracking_service = JobTrackingService()