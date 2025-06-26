"""
SQLAlchemy models that match the existing database schema.
These models work with the current database structure without requiring migrations.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DECIMAL, DateTime, Date, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class ExistingCompany(Base):
    """Company model matching existing database schema."""
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), index=True)
    industry = Column(String(100), index=True)
    company_size = Column(String(50))
    headquarters_location = Column(String(255))
    founded_year = Column(Integer)
    revenue_range = Column(String(50))
    description = Column(Text)
    logo_url = Column(Text)
    linkedin_company_id = Column(Integer, index=True)
    glassdoor_company_id = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    job_postings = relationship("ExistingJobPosting", back_populates="company")


class ExistingLocation(Base):
    """Location model matching existing database schema."""
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    city = Column(String(100), index=True)
    state = Column(String(100), index=True)
    country = Column(String(100), nullable=False, index=True)
    latitude = Column(DECIMAL(10, 8))
    longitude = Column(DECIMAL(11, 8))
    metro_area = Column(String(150))
    timezone = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    job_postings = relationship("ExistingJobPosting", back_populates="location")


class ExistingJobCategory(Base):
    """Job category model matching existing database schema."""
    __tablename__ = "job_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey('job_categories.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Self-referential relationship
    parent_category = relationship("ExistingJobCategory", remote_side=[id])
    subcategories = relationship("ExistingJobCategory")
    
    # Relationships
    job_postings = relationship("ExistingJobPosting", back_populates="job_category")


class ExistingJobPosting(Base):
    """Job posting model matching existing database schema."""
    __tablename__ = "job_postings"
    
    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(255), nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True, index=True)
    job_category_id = Column(Integer, ForeignKey('job_categories.id'), nullable=True, index=True)
    description = Column(Text)
    requirements = Column(Text)
    job_type = Column(String(50), index=True)
    experience_level = Column(String(50), index=True)
    salary_min = Column(DECIMAL(12, 2), index=True)
    salary_max = Column(DECIMAL(12, 2), index=True)
    salary_currency = Column(String(3))
    salary_interval = Column(String(20))
    is_remote = Column(Boolean, index=True)
    easy_apply = Column(Boolean)
    job_url = Column(Text, nullable=False)
    application_url = Column(Text)
    source_platform = Column(String(50), nullable=False, index=True)
    date_posted = Column(Date, index=True)
    date_scraped = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    last_seen = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_active = Column(Boolean, nullable=False, index=True)
    skills = Column(ARRAY(String))
    job_metadata = Column('metadata', JSON)
    
    # Relationships
    company = relationship("ExistingCompany", back_populates="job_postings")
    location = relationship("ExistingLocation", back_populates="job_postings")
    job_category = relationship("ExistingJobCategory", back_populates="job_postings")
    job_metrics = relationship("ExistingJobMetrics", back_populates="job_posting", uselist=False)


class ExistingJobMetrics(Base):
    """Job metrics model matching existing database schema."""
    __tablename__ = "job_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    job_posting_id = Column(Integer, ForeignKey('job_postings.id'), nullable=False, unique=True)
    view_count = Column(Integer, nullable=False)
    application_count = Column(Integer, nullable=False)
    save_count = Column(Integer, nullable=False)
    search_appearance_count = Column(Integer, nullable=False)
    last_updated = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Fields for robust repost and evergreen tracking
    repost_count = Column(Integer, nullable=False, default=0, index=True)
    is_evergreen = Column(Boolean, nullable=False, default=False, index=True)
    evergreen_score = Column(Integer, nullable=False, default=0, index=True)
    
    # Relationships
    job_posting = relationship("ExistingJobPosting", back_populates="job_metrics")