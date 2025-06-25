"""
Scheduled search models for persistent testing across deployments.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class ScheduledSearch(Base):
    """Persistent scheduled searches for ongoing testing."""
    __tablename__ = "scheduled_searches"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Search parameters
    search_term = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    site = Column(String(50), nullable=False, default="indeed")
    results_wanted = Column(Integer, default=10)
    
    # Scheduling
    frequency_hours = Column(Integer, default=24)  # Run every 24 hours
    active = Column(Boolean, default=True, index=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_run_at = Column(DateTime, nullable=True, index=True)
    next_run_at = Column(DateTime, nullable=True, index=True)
    
    # Statistics
    total_runs = Column(Integer, default=0)
    total_jobs_found = Column(Integer, default=0)
    total_duplicates = Column(Integer, default=0)
    
    # Relationships
    test_runs = relationship("TestRun", back_populates="scheduled_search", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ScheduledSearch(name='{self.name}', search_term='{self.search_term}')>"


class TestRun(Base):
    """Individual test run results for tracking over time."""
    __tablename__ = "test_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    scheduled_search_id = Column(Integer, ForeignKey('scheduled_searches.id'), nullable=False, index=True)
    
    # Test execution details
    test_name = Column(String(255), nullable=False)
    status = Column(String(50), default="success", index=True)  # success, failed, timeout
    
    # Results
    jobs_found = Column(Integer, default=0)
    duplicates_detected = Column(Integer, default=0)
    new_jobs = Column(Integer, default=0)
    cached_results = Column(Boolean, default=False)
    
    # Performance metrics
    execution_time_ms = Column(Integer, nullable=True)
    api_response_time_ms = Column(Integer, nullable=True)
    
    # Data storage
    raw_results = Column(JSON, nullable=True)  # Store full API response for analysis
    error_message = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    server_version = Column(String(50), nullable=True)  # Track which version ran the test
    
    # Relationships
    scheduled_search = relationship("ScheduledSearch", back_populates="test_runs")
    
    def __repr__(self):
        return f"<TestRun(test_name='{self.test_name}', status='{self.status}', jobs_found={self.jobs_found})>"


class TestConfiguration(Base):
    """Global test configuration that persists across deployments."""
    __tablename__ = "test_configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<TestConfiguration(key='{self.key}')>"