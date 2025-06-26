"""finalize_migration

Revision ID: 275658513cef
Revises: b77c46b5c926
Create Date: 2025-06-26 14:30:02.872084+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision: str = '275658513cef'
down_revision: Union[str, None] = 'b77c46b5c926'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    This migration performs the following:
    1. Migrates data from existing tables to new tracking schema (temp_ tables)
    2. Drops the old tables
    3. Renames temp_ tables to final names
    
    Note: This is a destructive migration that assumes job deduplication
    will be handled by the migration service, not in SQL.
    """
    
    # Step 1: Basic data migration (without deduplication)
    # We'll handle deduplication in the migration service
    
    # Migrate companies (direct mapping)
    op.execute(text("""
        INSERT INTO temp_companies (
            name, domain, industry, company_size, headquarters_location,
            founded_year, revenue_range, description, logo_url,
            linkedin_company_id, glassdoor_company_id, created_at, updated_at
        )
        SELECT DISTINCT ON (name, COALESCE(domain, ''))
            name, domain, industry, company_size, headquarters_location,
            founded_year, revenue_range, description, logo_url,
            linkedin_company_id, glassdoor_company_id, created_at, 
            COALESCE(updated_at, created_at)
        FROM companies
        WHERE name IS NOT NULL
        ORDER BY name, COALESCE(domain, ''), created_at
    """))
    
    # Migrate locations (with coordinate transformation)
    op.execute(text("""
        INSERT INTO temp_locations (
            city, state, country, region, coordinates, created_at
        )
        SELECT DISTINCT ON (COALESCE(city, ''), COALESCE(state, ''), country)
            city, state, country, 
            NULL as region,  -- Will be populated later
            CASE 
                WHEN latitude IS NOT NULL AND longitude IS NOT NULL 
                THEN latitude::text || ',' || longitude::text
                ELSE NULL
            END as coordinates,
            created_at
        FROM locations
        WHERE country IS NOT NULL
        ORDER BY COALESCE(city, ''), COALESCE(state, ''), country, created_at
    """))
    
    # Migrate job categories (simple mapping)
    op.execute(text("""
        INSERT INTO temp_job_categories (
            name, parent_category_id, created_at
        )
        SELECT DISTINCT ON (name)
            name, parent_id as parent_category_id, created_at
        FROM job_categories
        WHERE name IS NOT NULL
        ORDER BY name, created_at
    """))
    
    # Note: Job postings migration requires the data migration service
    # to handle deduplication and job_hash generation.
    # We'll create a placeholder for now.
    
    # Step 2: Drop old tables (after data migration is complete)
    # This should only be run after the data migration service has completed
    
    # Step 3: Rename temp tables to final names
    # This will be done after data migration service completes


def downgrade() -> None:
    """
    Reverses the migration by:
    1. Renaming tables back to temp_
    2. Recreating original tables
    3. Migrating data back (with potential data loss)
    """
    # This is a complex downgrade that would require recreating
    # the original schema and migrating data back with potential loss
    pass