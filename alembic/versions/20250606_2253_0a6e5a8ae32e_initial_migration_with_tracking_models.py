"""Initial migration with tracking models

Revision ID: 0a6e5a8ae32e
Revises: 
Create Date: 2025-06-06 22:53:23.354540+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a6e5a8ae32e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create companies table
    op.create_table('companies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('domain', sa.String(length=255), nullable=True),
    sa.Column('industry', sa.String(length=100), nullable=True),
    sa.Column('company_size', sa.String(length=50), nullable=True),
    sa.Column('headquarters_location', sa.String(length=255), nullable=True),
    sa.Column('founded_year', sa.Integer(), nullable=True),
    sa.Column('revenue_range', sa.String(length=50), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('logo_url', sa.Text(), nullable=True),
    sa.Column('linkedin_company_id', sa.Integer(), nullable=True),
    sa.Column('glassdoor_company_id', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'domain', name='uq_company_name_domain')
    )
    op.create_index('idx_company_name_industry', 'companies', ['name', 'industry'], unique=False)
    op.create_index(op.f('ix_companies_domain'), 'companies', ['domain'], unique=False)
    op.create_index(op.f('ix_companies_id'), 'companies', ['id'], unique=False)
    op.create_index(op.f('ix_companies_industry'), 'companies', ['industry'], unique=False)
    op.create_index(op.f('ix_companies_linkedin_company_id'), 'companies', ['linkedin_company_id'], unique=False)
    op.create_index(op.f('ix_companies_name'), 'companies', ['name'], unique=False)

    # Create job_categories table
    op.create_table('job_categories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['parent_id'], ['job_categories.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', name='uq_job_category_name')
    )
    op.create_index(op.f('ix_job_categories_id'), 'job_categories', ['id'], unique=False)
    op.create_index(op.f('ix_job_categories_name'), 'job_categories', ['name'], unique=False)

    # Create locations table
    op.create_table('locations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('state', sa.String(length=100), nullable=True),
    sa.Column('country', sa.String(length=100), nullable=False),
    sa.Column('latitude', sa.DECIMAL(precision=10, scale=8), nullable=True),
    sa.Column('longitude', sa.DECIMAL(precision=11, scale=8), nullable=True),
    sa.Column('metro_area', sa.String(length=150), nullable=True),
    sa.Column('timezone', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('city', 'state', 'country', name='uq_location_city_state_country')
    )
    op.create_index('idx_location_city_country', 'locations', ['city', 'country'], unique=False)
    op.create_index(op.f('ix_locations_city'), 'locations', ['city'], unique=False)
    op.create_index(op.f('ix_locations_country'), 'locations', ['country'], unique=False)
    op.create_index(op.f('ix_locations_id'), 'locations', ['id'], unique=False)
    op.create_index(op.f('ix_locations_state'), 'locations', ['state'], unique=False)

    # Create job_postings table
    op.create_table('job_postings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('external_id', sa.String(length=255), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.Column('location_id', sa.Integer(), nullable=True),
    sa.Column('job_category_id', sa.Integer(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('requirements', sa.Text(), nullable=True),
    sa.Column('job_type', sa.String(length=50), nullable=True),
    sa.Column('experience_level', sa.String(length=50), nullable=True),
    sa.Column('salary_min', sa.DECIMAL(precision=12, scale=2), nullable=True),
    sa.Column('salary_max', sa.DECIMAL(precision=12, scale=2), nullable=True),
    sa.Column('salary_currency', sa.String(length=3), nullable=True),
    sa.Column('salary_interval', sa.String(length=20), nullable=True),
    sa.Column('is_remote', sa.Boolean(), nullable=True),
    sa.Column('easy_apply', sa.Boolean(), nullable=True),
    sa.Column('job_url', sa.Text(), nullable=False),
    sa.Column('application_url', sa.Text(), nullable=True),
    sa.Column('source_platform', sa.String(length=50), nullable=False),
    sa.Column('date_posted', sa.Date(), nullable=True),
    sa.Column('date_scraped', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
    sa.Column('skills', sa.ARRAY(sa.String()), nullable=True),
    sa.Column('metadata', sa.JSON(), nullable=True),
    sa.CheckConstraint('salary_min <= salary_max', name='ck_salary_range'),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.ForeignKeyConstraint(['job_category_id'], ['job_categories.id'], ),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('external_id', 'source_platform', name='uq_job_external_id_platform')
    )
    op.create_index('idx_job_posting_active_scraped', 'job_postings', ['is_active', 'date_scraped'], unique=False)
    op.create_index('idx_job_posting_location_active', 'job_postings', ['location_id', 'is_active'], unique=False)
    op.create_index('idx_job_posting_posted_platform', 'job_postings', ['date_posted', 'source_platform'], unique=False)
    op.create_index('idx_job_posting_salary_range', 'job_postings', ['salary_min', 'salary_max'], unique=False)
    op.create_index('idx_job_posting_title_company', 'job_postings', ['title', 'company_id'], unique=False)
    op.create_index(op.f('ix_job_postings_company_id'), 'job_postings', ['company_id'], unique=False)
    op.create_index(op.f('ix_job_postings_date_posted'), 'job_postings', ['date_posted'], unique=False)
    op.create_index(op.f('ix_job_postings_date_scraped'), 'job_postings', ['date_scraped'], unique=False)
    op.create_index(op.f('ix_job_postings_external_id'), 'job_postings', ['external_id'], unique=False)
    op.create_index(op.f('ix_job_postings_id'), 'job_postings', ['id'], unique=False)
    op.create_index(op.f('ix_job_postings_is_active'), 'job_postings', ['is_active'], unique=False)
    op.create_index(op.f('ix_job_postings_source_platform'), 'job_postings', ['source_platform'], unique=False)
    op.create_index(op.f('ix_job_postings_title'), 'job_postings', ['title'], unique=False)

    # Create job_sources table
    op.create_table('job_sources',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('base_url', sa.String(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
    sa.Column('rate_limit_per_minute', sa.Integer(), nullable=True),
    sa.Column('requires_auth', sa.Boolean(), nullable=False, default=False),
    sa.Column('api_endpoint', sa.String(length=255), nullable=True),
    sa.Column('scraping_config', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', name='uq_job_source_name')
    )
    op.create_index(op.f('ix_job_sources_id'), 'job_sources', ['id'], unique=False)
    op.create_index(op.f('ix_job_sources_is_active'), 'job_sources', ['is_active'], unique=False)
    op.create_index(op.f('ix_job_sources_name'), 'job_sources', ['name'], unique=False)

    # Create job_metrics table
    op.create_table('job_metrics',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('job_posting_id', sa.Integer(), nullable=False),
    sa.Column('view_count', sa.Integer(), nullable=False, default=0),
    sa.Column('application_count', sa.Integer(), nullable=False, default=0),
    sa.Column('save_count', sa.Integer(), nullable=False, default=0),
    sa.Column('search_appearance_count', sa.Integer(), nullable=False, default=0),
    sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('job_posting_id', name='uq_job_metrics_posting')
    )
    op.create_index(op.f('ix_job_metrics_id'), 'job_metrics', ['id'], unique=False)
    op.create_index(op.f('ix_job_metrics_job_posting_id'), 'job_metrics', ['job_posting_id'], unique=False)

    # Create company_hiring_trends table (TimescaleDB hypertable)
    op.create_table('company_hiring_trends',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('new_job_postings', sa.Integer(), nullable=False, default=0),
    sa.Column('total_active_postings', sa.Integer(), nullable=False, default=0),
    sa.Column('expired_postings', sa.Integer(), nullable=False, default=0),
    sa.Column('avg_days_to_fill', sa.DECIMAL(precision=5, scale=2), nullable=True),
    sa.Column('top_job_categories', sa.ARRAY(sa.String()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('company_id', 'date', name='uq_company_trend_date')
    )
    op.create_index('idx_company_hiring_trends_date', 'company_hiring_trends', ['date'], unique=False)
    op.create_index(op.f('ix_company_hiring_trends_company_id'), 'company_hiring_trends', ['company_id'], unique=False)
    op.create_index(op.f('ix_company_hiring_trends_id'), 'company_hiring_trends', ['id'], unique=False)

    # Create scraping_runs table
    op.create_table('scraping_runs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('source_platform', sa.String(length=50), nullable=False),
    sa.Column('search_terms', sa.ARRAY(sa.String()), nullable=True),
    sa.Column('locations', sa.ARRAY(sa.String()), nullable=True),
    sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('jobs_found', sa.Integer(), nullable=False, default=0),
    sa.Column('jobs_processed', sa.Integer(), nullable=False, default=0),
    sa.Column('jobs_skipped', sa.Integer(), nullable=False, default=0),
    sa.Column('error_count', sa.Integer(), nullable=False, default=0),
    sa.Column('error_details', sa.JSON(), nullable=True),
    sa.Column('config_used', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'failed', 'cancelled')", name='ck_scraping_run_status'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_scraping_run_platform_status', 'scraping_runs', ['source_platform', 'status'], unique=False)
    op.create_index('idx_scraping_run_start_time', 'scraping_runs', ['start_time'], unique=False)
    op.create_index(op.f('ix_scraping_runs_id'), 'scraping_runs', ['id'], unique=False)
    op.create_index(op.f('ix_scraping_runs_source_platform'), 'scraping_runs', ['source_platform'], unique=False)
    op.create_index(op.f('ix_scraping_runs_status'), 'scraping_runs', ['status'], unique=False)

    # Create webhook_subscriptions table
    op.create_table('webhook_subscriptions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('url', sa.String(length=500), nullable=False),
    sa.Column('event_types', sa.ARRAY(sa.String()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
    sa.Column('secret_key', sa.String(length=255), nullable=True),
    sa.Column('retry_count', sa.Integer(), nullable=False, default=3),
    sa.Column('timeout_seconds', sa.Integer(), nullable=False, default=30),
    sa.Column('last_triggered', sa.DateTime(timezone=True), nullable=True),
    sa.Column('failure_count', sa.Integer(), nullable=False, default=0),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_webhook_subscriptions_id'), 'webhook_subscriptions', ['id'], unique=False)
    op.create_index(op.f('ix_webhook_subscriptions_is_active'), 'webhook_subscriptions', ['is_active'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order of creation
    op.drop_table('webhook_subscriptions')
    op.drop_table('scraping_runs')
    op.drop_table('company_hiring_trends')
    op.drop_table('job_metrics')
    op.drop_table('job_sources')
    op.drop_table('job_postings')
    op.drop_table('locations')
    op.drop_table('job_categories')
    op.drop_table('companies')