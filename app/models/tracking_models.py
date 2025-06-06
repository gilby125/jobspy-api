"""
SQLAlchemy models for job tracking system with TimescaleDB optimization.
"""
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DECIMAL, DateTime, Date,
    ForeignKey, Index, UniqueConstraint, CheckConstraint, ARRAY
)
from sqlalchemy.dialects.postgresql import JSONB, POINT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Company(Base):
    """Company information with normalized data to prevent duplication."""
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), index=True)
    industry = Column(String(100), index=True)
    company_size = Column(String(50))  # e.g., "1-10", "11-50", "51-200", etc.
    headquarters_location = Column(String(255))
    founded_year = Column(Integer)
    revenue_range = Column(String(50))  # e.g., "$1M-$10M", "$10M-$50M"
    description = Column(Text)
    logo_url = Column(Text)
    
    # External IDs for data enrichment
    linkedin_company_id = Column(Integer, index=True)
    glassdoor_company_id = Column(String(50))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    job_postings = relationship("JobPosting", back_populates="company")
    hiring_trends = relationship("CompanyHiringTrend", back_populates="company")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('name', 'domain', name='uq_company_name_domain'),
        Index('idx_company_name_industry', 'name', 'industry'),
    )


class JobCategory(Base):
    """Hierarchical job categories/functions."""
    __tablename__ = "job_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    parent_category_id = Column(Integer, ForeignKey('job_categories.id'), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Self-referential relationship
    parent_category = relationship("JobCategory", remote_side=[id])
    subcategories = relationship("JobCategory")
    
    # Relationships
    job_postings = relationship("JobPosting", back_populates="job_category")


class Location(Base):
    """Geographic locations for job postings."""
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    city = Column(String(100), index=True)
    state = Column(String(100), index=True)
    country = Column(String(100), nullable=False, index=True)
    region = Column(String(100))  # e.g., "North America", "Europe"
    
    # PostGIS point for future geographic queries
    coordinates = Column(POINT)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    job_postings = relationship("JobPosting", back_populates="location")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('city', 'state', 'country', name='uq_location'),
        Index('idx_location_country_state', 'country', 'state'),
    )


class JobPosting(Base):
    """
    Core job posting data with unique identification.
    This is the main entity that prevents job duplication.
    """
    __tablename__ = "job_postings"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Unique hash for deduplication (SHA-256 of normalized job content)
    job_hash = Column(String(64), nullable=False, unique=True, index=True)
    
    # Core job information
    title = Column(String(500), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True, index=True)
    job_category_id = Column(Integer, ForeignKey('job_categories.id'), nullable=True, index=True)
    
    # Job characteristics
    job_type = Column(String(50), index=True)  # fulltime, parttime, contract, internship
    experience_level = Column(String(50), index=True)  # entry, mid, senior, executive
    is_remote = Column(Boolean, default=False, index=True)
    
    # Job content
    description = Column(Text)
    requirements = Column(Text)
    
    # Salary information (normalized to decimal for analytics)
    salary_min = Column(DECIMAL(12, 2), index=True)
    salary_max = Column(DECIMAL(12, 2), index=True)
    salary_currency = Column(String(3), default='USD')
    salary_interval = Column(String(20))  # yearly, monthly, hourly
    
    # Tracking timestamps
    first_seen_at = Column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Job status
    status = Column(String(20), default='active', index=True)  # active, expired, filled
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="job_postings")
    location = relationship("Location", back_populates="job_postings")
    job_category = relationship("JobCategory", back_populates="job_postings")
    job_sources = relationship("JobSource", back_populates="job_posting", cascade="all, delete-orphan")
    job_metrics = relationship("JobMetrics", back_populates="job_posting", uselist=False)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_job_posting_company_status', 'company_id', 'status'),
        Index('idx_job_posting_location_type', 'location_id', 'job_type'),
        Index('idx_job_posting_salary_range', 'salary_min', 'salary_max'),
        Index('idx_job_posting_dates', 'first_seen_at', 'last_seen_at'),
        CheckConstraint('salary_min <= salary_max', name='chk_salary_range'),
        CheckConstraint('first_seen_at <= last_seen_at', name='chk_date_range'),
    )


class JobSource(Base):
    """
    Track where jobs are posted across different platforms.
    Allows the same job to be tracked across multiple sites.
    """
    __tablename__ = "job_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    job_posting_id = Column(Integer, ForeignKey('job_postings.id'), nullable=False, index=True)
    
    # Source platform information
    source_site = Column(String(50), nullable=False, index=True)  # indeed, linkedin, etc.
    external_job_id = Column(String(255), index=True)  # Job ID from the source site
    job_url = Column(Text, nullable=False)
    
    # Source-specific data
    post_date = Column(Date, index=True)
    apply_url = Column(Text)
    easy_apply = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    job_posting = relationship("JobPosting", back_populates="job_sources")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('source_site', 'external_job_id', name='uq_source_external_id'),
        UniqueConstraint('job_posting_id', 'source_site', name='uq_job_source_site'),
        Index('idx_job_source_site_date', 'source_site', 'post_date'),
    )


class JobMetrics(Base):
    """
    Aggregated metrics for each job posting.
    Updated whenever job activity is detected.
    """
    __tablename__ = "job_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    job_posting_id = Column(Integer, ForeignKey('job_postings.id'), nullable=False, unique=True)
    
    # Activity metrics
    total_seen_count = Column(Integer, default=1, nullable=False)
    sites_posted_count = Column(Integer, default=1, nullable=False)
    days_active = Column(Integer, default=0, nullable=False)
    repost_count = Column(Integer, default=0, nullable=False)
    
    # Activity tracking
    last_activity_date = Column(Date, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    job_posting = relationship("JobPosting", back_populates="job_metrics")


class CompanyHiringTrend(Base):
    """
    Time-series data for company hiring trends.
    This table will be converted to a TimescaleDB hypertable.
    """
    __tablename__ = "company_hiring_trends"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # Daily metrics
    new_jobs_count = Column(Integer, default=0)
    active_jobs_count = Column(Integer, default=0)
    filled_jobs_count = Column(Integer, default=0)
    
    # Salary trends
    avg_salary_min = Column(DECIMAL(12, 2))
    avg_salary_max = Column(DECIMAL(12, 2))
    
    # Popular job category for the day
    top_job_category_id = Column(Integer, ForeignKey('job_categories.id'))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="hiring_trends")
    top_job_category = relationship("JobCategory")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('company_id', 'date', name='uq_company_date'),
        Index('idx_hiring_trend_date', 'date'),
        Index('idx_hiring_trend_company_date', 'company_id', 'date'),
    )


class ScrapingRun(Base):
    """
    Track execution of scraping workers.
    Useful for monitoring and debugging scraping operations.
    """
    __tablename__ = "scraping_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    source_site = Column(String(50), nullable=False, index=True)
    search_params = Column(JSONB, nullable=False)  # Store search parameters as JSON
    
    # Execution status
    status = Column(String(20), nullable=False, index=True)  # pending, running, completed, failed
    
    # Results
    jobs_found = Column(Integer, default=0)
    jobs_new = Column(Integer, default=0)
    jobs_updated = Column(Integer, default=0)
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True))
    
    # Error handling
    error_message = Column(Text)
    worker_id = Column(String(100))  # Celery worker ID
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_scraping_run_site_status', 'source_site', 'status'),
        Index('idx_scraping_run_started', 'started_at'),
    )


class WebhookSubscription(Base):
    """
    Webhook subscriptions for real-time notifications.
    """
    __tablename__ = "webhook_subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    
    # Event configuration
    events = Column(ARRAY(String), nullable=False)  # ["new_job", "company_trend", etc.]
    filters = Column(JSONB)  # JSON filters for companies, locations, etc.
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    
    # Security
    secret_key = Column(String(255))  # For webhook signature verification
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_webhook_active_events', 'is_active', 'events'),
    )