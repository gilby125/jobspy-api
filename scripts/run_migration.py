#!/usr/bin/env python3
"""
Script to run the data migration from the old schema to the new tracking schema.

This script should be run after the Alembic migrations have created the temp_ tables
but before finalizing the migration by dropping old tables and renaming temp_ tables.

Usage:
    python scripts/run_migration.py
    python scripts/run_migration.py --finalize  # To complete migration
"""
import os
import sys
import logging
from datetime import datetime

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.db.database import init_database, SessionLocal
from app.models.existing_models import Base as ExistingBase
from app.models.tracking_models import Base as TrackingBase
from app.services.migration_service import migration_service
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_prerequisites(db_session):
    """Check that temp tables exist before migration."""
    logger.info("Checking prerequisites...")
    
    required_tables = [
        'temp_companies', 'temp_locations', 'temp_job_categories',
        'temp_job_postings', 'temp_job_sources', 'temp_job_metrics'
    ]
    
    for table in required_tables:
        result = db_session.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = :table_name
                )
            """),
            {'table_name': table}
        )
        exists = result.scalar()
        
        if not exists:
            raise RuntimeError(f"Required table '{table}' does not exist. Run Alembic migrations first.")
    
    logger.info("All prerequisite tables exist.")


def run_migration():
    """Execute the full data migration."""
    start_time = datetime.utcnow()
    logger.info(f"Starting migration at {start_time}")
    
    # Initialize database
    init_database()
    
    try:
        with SessionLocal() as db:
            # Check prerequisites
            check_prerequisites(db)
            
            # Run the migration
            migration_service.migrate_all_data(db)
            
            # Show migration statistics
            end_time = datetime.utcnow()
            duration = end_time - start_time
            
            logger.info(f"Migration completed in {duration}")
            logger.info(f"Migrated {len(migration_service.company_map)} companies")
            logger.info(f"Migrated {len(migration_service.location_map)} locations")
            logger.info(f"Migrated {len(migration_service.category_map)} job categories")
            logger.info(f"Created {len(migration_service.job_hash_map)} unique jobs from {len(migration_service.processed_jobs)} total jobs")
            
            # Verify data in temp tables
            job_count = db.execute(text("SELECT COUNT(*) FROM temp_job_postings")).scalar()
            source_count = db.execute(text("SELECT COUNT(*) FROM temp_job_sources")).scalar()
            metrics_count = db.execute(text("SELECT COUNT(*) FROM temp_job_metrics")).scalar()
            
            logger.info(f"Verification - Jobs: {job_count}, Sources: {source_count}, Metrics: {metrics_count}")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    
    logger.info("\nMigration data loaded successfully!")
    logger.info("Next steps:")
    logger.info("1. Review the migrated data in temp_ tables")
    logger.info("2. Run 'python scripts/run_migration.py --finalize' to complete the migration")


def finalize_migration():
    """
    Finalize the migration by dropping old tables and renaming temp tables.
    This is a separate function to be run after verifying the migration.
    """
    logger.info("Finalizing migration...")
    
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.begin() as conn:
        # Drop old tables
        logger.info("Dropping old tables...")
        conn.execute(text("DROP TABLE IF EXISTS job_metrics CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS job_postings CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS job_categories CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS locations CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS companies CASCADE"))
        
        # Rename temp tables to final names
        logger.info("Renaming temp tables to final names...")
        conn.execute(text("ALTER TABLE temp_companies RENAME TO companies"))
        conn.execute(text("ALTER TABLE temp_locations RENAME TO locations"))
        conn.execute(text("ALTER TABLE temp_job_categories RENAME TO job_categories"))
        conn.execute(text("ALTER TABLE temp_job_postings RENAME TO job_postings"))
        conn.execute(text("ALTER TABLE temp_job_sources RENAME TO job_sources"))
        conn.execute(text("ALTER TABLE temp_job_metrics RENAME TO job_metrics"))
        conn.execute(text("ALTER TABLE temp_company_hiring_trends RENAME TO company_hiring_trends"))
        conn.execute(text("ALTER TABLE temp_scraping_runs RENAME TO scraping_runs"))
        conn.execute(text("ALTER TABLE temp_webhook_subscriptions RENAME TO webhook_subscriptions"))
        
        # Rename constraints and indexes
        logger.info("Renaming constraints and indexes...")
        
        # Update constraint names
        rename_queries = [
            # Companies constraints
            "ALTER TABLE companies RENAME CONSTRAINT uq_temp_company_name_domain TO uq_company_name_domain",
            
            # Locations constraints  
            "ALTER TABLE locations RENAME CONSTRAINT uq_temp_location TO uq_location",
            
            # Job sources constraints
            "ALTER TABLE job_sources RENAME CONSTRAINT uq_temp_source_external_id TO uq_source_external_id",
            "ALTER TABLE job_sources RENAME CONSTRAINT uq_temp_job_source_site TO uq_job_source_site",
            
            # Company hiring trends constraints
            "ALTER TABLE company_hiring_trends RENAME CONSTRAINT uq_temp_company_date TO uq_company_date",
            
            # Job postings constraints
            "ALTER TABLE job_postings RENAME CONSTRAINT chk_temp_salary_range TO chk_salary_range",
            "ALTER TABLE job_postings RENAME CONSTRAINT chk_temp_date_range TO chk_date_range",
        ]
        
        for query in rename_queries:
            try:
                conn.execute(text(query))
            except Exception as e:
                logger.warning(f"Could not rename constraint: {e}")
        
        # Rename indexes
        index_renames = [
            # Simple renames (remove temp_ prefix)
            ("ix_temp_companies_id", "ix_companies_id"),
            ("ix_temp_companies_name", "ix_companies_name"),
            ("ix_temp_companies_domain", "ix_companies_domain"),
            ("ix_temp_companies_industry", "ix_companies_industry"),
            ("ix_temp_companies_linkedin_company_id", "ix_companies_linkedin_company_id"),
            ("idx_temp_company_name_industry", "idx_company_name_industry"),
            
            ("ix_temp_locations_id", "ix_locations_id"),
            ("ix_temp_locations_city", "ix_locations_city"),
            ("ix_temp_locations_state", "ix_locations_state"),
            ("ix_temp_locations_country", "ix_locations_country"),
            ("idx_temp_location_country_state", "idx_location_country_state"),
            
            ("ix_temp_job_categories_id", "ix_job_categories_id"),
            ("ix_temp_job_categories_name", "ix_job_categories_name"),
            
            ("ix_temp_job_postings_id", "ix_job_postings_id"),
            ("ix_temp_job_postings_job_hash", "ix_job_postings_job_hash"),
            ("ix_temp_job_postings_title", "ix_job_postings_title"),
            ("ix_temp_job_postings_company_id", "ix_job_postings_company_id"),
            ("ix_temp_job_postings_location_id", "ix_job_postings_location_id"),
            ("ix_temp_job_postings_job_category_id", "ix_job_postings_job_category_id"),
            ("ix_temp_job_postings_job_type", "ix_job_postings_job_type"),
            ("ix_temp_job_postings_experience_level", "ix_job_postings_experience_level"),
            ("ix_temp_job_postings_is_remote", "ix_job_postings_is_remote"),
            ("ix_temp_job_postings_salary_min", "ix_job_postings_salary_min"),
            ("ix_temp_job_postings_salary_max", "ix_job_postings_salary_max"),
            ("ix_temp_job_postings_first_seen_at", "ix_job_postings_first_seen_at"),
            ("ix_temp_job_postings_last_seen_at", "ix_job_postings_last_seen_at"),
            ("ix_temp_job_postings_status", "ix_job_postings_status"),
            ("idx_temp_job_posting_company_status", "idx_job_posting_company_status"),
            ("idx_temp_job_posting_location_type", "idx_job_posting_location_type"),
            ("idx_temp_job_posting_salary_range", "idx_job_posting_salary_range"),
            ("idx_temp_job_posting_dates", "idx_job_posting_dates"),
            
            ("ix_temp_job_sources_id", "ix_job_sources_id"),
            ("ix_temp_job_sources_job_posting_id", "ix_job_sources_job_posting_id"),
            ("ix_temp_job_sources_source_site", "ix_job_sources_source_site"),
            ("ix_temp_job_sources_external_job_id", "ix_job_sources_external_job_id"),
            ("ix_temp_job_sources_post_date", "ix_job_sources_post_date"),
            ("idx_temp_job_source_site_date", "idx_job_source_site_date"),
            
            ("ix_temp_job_metrics_id", "ix_job_metrics_id"),
            ("ix_temp_job_metrics_last_activity_date", "ix_job_metrics_last_activity_date"),
            
            ("ix_temp_company_hiring_trends_id", "ix_company_hiring_trends_id"),
            ("ix_temp_company_hiring_trends_company_id", "ix_company_hiring_trends_company_id"),
            ("ix_temp_company_hiring_trends_date", "ix_company_hiring_trends_date"),
            ("idx_temp_hiring_trend_date", "idx_hiring_trend_date"),
            ("idx_temp_hiring_trend_company_date", "idx_hiring_trend_company_date"),
            
            ("ix_temp_scraping_runs_id", "ix_scraping_runs_id"),
            ("ix_temp_scraping_runs_source_site", "ix_scraping_runs_source_site"),
            ("ix_temp_scraping_runs_status", "ix_scraping_runs_status"),
            ("ix_temp_scraping_runs_started_at", "ix_scraping_runs_started_at"),
            ("idx_temp_scraping_run_site_status", "idx_scraping_run_site_status"),
            ("idx_temp_scraping_run_started", "idx_scraping_run_started"),
            
            ("ix_temp_webhook_subscriptions_id", "ix_webhook_subscriptions_id"),
            ("ix_temp_webhook_subscriptions_is_active", "ix_webhook_subscriptions_is_active"),
            ("idx_temp_webhook_active_events", "idx_webhook_active_events"),
        ]
        
        for old_name, new_name in index_renames:
            try:
                conn.execute(text(f"ALTER INDEX {old_name} RENAME TO {new_name}"))
            except Exception as e:
                logger.warning(f"Could not rename index {old_name}: {e}")
    
    logger.info("Migration finalized successfully!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run data migration to new tracking schema")
    parser.add_argument(
        '--finalize', 
        action='store_true', 
        help='Finalize the migration by dropping old tables and renaming temp tables'
    )
    
    args = parser.parse_args()
    
    if args.finalize:
        try:
            response = input("This will DROP all old tables and rename temp tables. Are you sure? (yes/no): ")
        except EOFError:
            response = "yes"  # Handle piped input
        
        if response.lower() == 'yes':
            finalize_migration()
        else:
            logger.info("Finalization cancelled.")
    else:
        run_migration()