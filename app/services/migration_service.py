"""
Service for migrating data from the old schema to the new tracking schema.
"""
import logging
from typing import Dict, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text, and_
from app.models.existing_models import (
    ExistingJobPosting, ExistingCompany, ExistingLocation, 
    ExistingJobCategory, ExistingJobMetrics
)
from app.models.tracking_models import (
    JobPosting, Company, Location, JobSource, JobMetrics,
    JobCategory, Base
)
from app.services.deduplication_service import deduplication_service

logger = logging.getLogger(__name__)

class MigrationService:
    """Service for migrating data between schemas with deduplication."""
    
    def __init__(self):
        self.company_map: Dict[int, int] = {}  # old_id -> new_id
        self.location_map: Dict[int, int] = {}  # old_id -> new_id
        self.category_map: Dict[int, int] = {}  # old_id -> new_id
        self.job_hash_map: Dict[str, int] = {}  # job_hash -> new_job_id
        self.processed_jobs: Set[int] = set()  # Track processed job IDs
    
    def migrate_all_data(self, db: Session):
        """Execute full migration from old schema to new tracking schema."""
        logger.info("Starting full data migration...")
        
        try:
            # 1. Migrate reference data first
            self._migrate_companies(db)
            self._migrate_locations(db)
            self._migrate_job_categories(db)
            
            # 2. Migrate job postings with deduplication
            self._migrate_job_postings_with_deduplication(db)
            
            # 3. Complete the schema swap
            self._finalize_migration(db)
            
            logger.info("Migration completed successfully!")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            db.rollback()
            raise
    
    def _migrate_companies(self, db: Session):
        """Migrate companies from old to new schema."""
        logger.info("Migrating companies...")
        
        # Query is already in the Alembic migration, but we need to track IDs
        existing_companies = db.query(ExistingCompany).all()
        
        for old_company in existing_companies:
            # Check if already migrated
            new_company = db.query(Company.__table__.c.id).filter(
                Company.__table__.c.name == old_company.name,
                Company.__table__.c.domain == old_company.domain
            ).first()
            
            if new_company:
                self.company_map[old_company.id] = new_company.id
            
        logger.info(f"Mapped {len(self.company_map)} companies")
    
    def _migrate_locations(self, db: Session):
        """Migrate locations from old to new schema."""
        logger.info("Migrating locations...")
        
        existing_locations = db.query(ExistingLocation).all()
        
        for old_location in existing_locations:
            # Build coordinates string
            coordinates = None
            if old_location.latitude and old_location.longitude:
                coordinates = f"{old_location.latitude},{old_location.longitude}"
            
            # Check if already migrated
            new_location = db.query(Location.__table__.c.id).filter(
                Location.__table__.c.city == old_location.city,
                Location.__table__.c.state == old_location.state,
                Location.__table__.c.country == old_location.country
            ).first()
            
            if new_location:
                self.location_map[old_location.id] = new_location.id
            
        logger.info(f"Mapped {len(self.location_map)} locations")
    
    def _migrate_job_categories(self, db: Session):
        """Migrate job categories from old to new schema."""
        logger.info("Migrating job categories...")
        
        existing_categories = db.query(ExistingJobCategory).all()
        
        for old_category in existing_categories:
            new_category = db.query(JobCategory.__table__.c.id).filter(
                JobCategory.__table__.c.name == old_category.name
            ).first()
            
            if new_category:
                self.category_map[old_category.id] = new_category.id
        
        logger.info(f"Mapped {len(self.category_map)} job categories")
    
    def _migrate_job_postings_with_deduplication(self, db: Session):
        """Migrate job postings with intelligent deduplication."""
        logger.info("Migrating job postings with deduplication...")
        
        # Group jobs by potential duplicates
        job_groups = self._group_jobs_for_deduplication(db)
        
        total_jobs = sum(len(group) for group in job_groups.values())
        logger.info(f"Processing {total_jobs} jobs in {len(job_groups)} unique groups")
        
        for job_hash, job_group in job_groups.items():
            self._migrate_job_group(job_hash, job_group, db)
            
        logger.info(f"Migrated {len(self.job_hash_map)} unique jobs from {len(self.processed_jobs)} total jobs")
    
    def _group_jobs_for_deduplication(self, db: Session) -> Dict[str, list]:
        """Group existing jobs by their hash for deduplication."""
        job_groups = defaultdict(list)
        
        existing_jobs = db.query(ExistingJobPosting).all()
        
        for job in existing_jobs:
            # Generate hash for this job
            job_data = {
                'title': job.title,
                'company': job.company.name if job.company else '',
                'location': f"{job.location.city}, {job.location.state}" if job.location else '',
                'job_type': job.job_type,
                'description': job.description
            }
            
            job_hash = deduplication_service.generate_job_hash(job_data)
            job_groups[job_hash].append(job)
        
        return job_groups
    
    def _migrate_job_group(self, job_hash: str, job_group: list, db: Session):
        """Migrate a group of duplicate jobs as a single job with multiple sources."""
        # Sort jobs by date_scraped to find the earliest
        job_group.sort(key=lambda j: j.date_scraped or datetime.utcnow())
        
        # Use the earliest job as the base
        base_job = job_group[0]
        
        # Calculate aggregated dates
        first_seen_at = min(j.date_scraped for j in job_group if j.date_scraped)
        last_seen_at = max(j.last_seen for j in job_group if j.last_seen)
        
        # Create the job posting
        try:
            # Map to new IDs
            new_company_id = self.company_map.get(base_job.company_id)
            new_location_id = self.location_map.get(base_job.location_id) if base_job.location_id else None
            new_category_id = self.category_map.get(base_job.job_category_id) if base_job.job_category_id else None
            
            if not new_company_id:
                logger.warning(f"Company ID {base_job.company_id} not found in mapping, skipping job")
                return
            
            # Insert job posting using temp tables
            result = db.execute(
                text("""
                    INSERT INTO temp_job_postings (
                        job_hash, title, company_id, location_id, job_category_id,
                        job_type, experience_level, is_remote, description, requirements,
                        salary_min, salary_max, salary_currency, salary_interval,
                        first_seen_at, last_seen_at, status, created_at, updated_at
                    ) VALUES (
                        :job_hash, :title, :company_id, :location_id, :job_category_id,
                        :job_type, :experience_level, :is_remote, :description, :requirements,
                        :salary_min, :salary_max, :salary_currency, :salary_interval,
                        :first_seen_at, :last_seen_at, :status, :created_at, :updated_at
                    ) RETURNING id
                """),
                {
                    'job_hash': job_hash,
                    'title': base_job.title,
                    'company_id': new_company_id,
                    'location_id': new_location_id,
                    'job_category_id': new_category_id,
                    'job_type': base_job.job_type,
                    'experience_level': base_job.experience_level,
                    'is_remote': base_job.is_remote,
                    'description': base_job.description,
                    'requirements': base_job.requirements,
                    'salary_min': base_job.salary_min,
                    'salary_max': base_job.salary_max,
                    'salary_currency': base_job.salary_currency or 'USD',
                    'salary_interval': base_job.salary_interval,
                    'first_seen_at': first_seen_at,
                    'last_seen_at': last_seen_at,
                    'status': 'active' if base_job.is_active else 'expired',
                    'created_at': base_job.date_scraped,
                    'updated_at': base_job.last_seen
                }
            )
            
            new_job_id = result.scalar()
            self.job_hash_map[job_hash] = new_job_id
            
            # Create job sources for each occurrence
            seen_sources = set()
            for job in job_group:
                source_key = (job.source_platform, job.external_id)
                if source_key not in seen_sources:
                    db.execute(
                        text("""
                            INSERT INTO temp_job_sources (
                                job_posting_id, source_site, external_job_id,
                                job_url, post_date, apply_url, easy_apply,
                                created_at, updated_at
                            ) VALUES (
                                :job_posting_id, :source_site, :external_job_id,
                                :job_url, :post_date, :apply_url, :easy_apply,
                                :created_at, :updated_at
                            )
                        """),
                        {
                            'job_posting_id': new_job_id,
                            'source_site': job.source_platform,
                            'external_job_id': job.external_id,
                            'job_url': job.job_url,
                            'post_date': job.date_posted,
                            'apply_url': job.application_url,
                            'easy_apply': job.easy_apply,
                            'created_at': job.date_scraped,
                            'updated_at': job.last_seen
                        }
                    )
                    seen_sources.add(source_key)
                
                self.processed_jobs.add(job.id)
            
            # Create job metrics
            days_active = (last_seen_at - first_seen_at).days if first_seen_at and last_seen_at else 0
            
            # Try to aggregate metrics from all jobs in the group
            total_seen_count = 0
            for job in job_group:
                if hasattr(job, 'job_metrics') and job.job_metrics:
                    total_seen_count += job.job_metrics.search_appearance_count or 0
            
            db.execute(
                text("""
                    INSERT INTO temp_job_metrics (
                        job_posting_id, total_seen_count, sites_posted_count,
                        days_active, repost_count, last_activity_date,
                        created_at, updated_at
                    ) VALUES (
                        :job_posting_id, :total_seen_count, :sites_posted_count,
                        :days_active, :repost_count, :last_activity_date,
                        :created_at, :updated_at
                    )
                """),
                {
                    'job_posting_id': new_job_id,
                    'total_seen_count': max(total_seen_count, len(job_group)),
                    'sites_posted_count': len(seen_sources),
                    'days_active': days_active,
                    'repost_count': max(0, len(job_group) - 1),  # Reposts = occurrences - 1
                    'last_activity_date': last_seen_at.date() if last_seen_at else datetime.utcnow().date(),
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }
            )
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error migrating job group {job_hash}: {e}")
            db.rollback()
            raise
    
    def _finalize_migration(self, db: Session):
        """Complete the migration by swapping tables."""
        logger.info("Finalizing migration...")
        
        # This will be handled by a separate script that:
        # 1. Drops the old tables
        # 2. Renames temp_ tables to final names
        # 3. Updates sequences
        
        logger.info("Migration finalization prepared. Run the finalization script to complete.")

# Global service instance
migration_service = MigrationService()