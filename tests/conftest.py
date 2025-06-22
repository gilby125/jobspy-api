"""Pytest configuration for JobSpy Docker API tests."""
import pytest
import os
import asyncio
import time
from datetime import datetime, timedelta
from typing import Generator, Dict, Any, List
from unittest.mock import MagicMock, AsyncMock, patch
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from app.main import app
from app.db.database import get_db
from app.models.tracking_models import Base, JobRequest, JobResult
from app.models.job_models import Job, JobSearchRequest
from app.core.config import settings

# Test database URL - use real PostgreSQL for tests
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://jobspy:jobspy_password@localhost:5432/test_jobspy")

@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine using real PostgreSQL."""
    engine = create_engine(
        TEST_DATABASE_URL,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False  # Set to True for SQL debugging
    )
    
    # Create all tables in test database
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Clean up - drop all tables after tests
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture
def test_db(test_engine):
    """Create a test database session."""
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def client(test_db):
    """Get a TestClient instance for the FastAPI app with test database."""
    def override_get_db():
        try:
            yield test_db
        finally:
            test_db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Disable authentication for tests
    original_auth = settings.ENABLE_API_KEY_AUTH
    settings.ENABLE_API_KEY_AUTH = False
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Restore original settings
    settings.ENABLE_API_KEY_AUTH = original_auth
    app.dependency_overrides.clear()

@pytest.fixture
def authenticated_client(test_db):
    """Get a TestClient with API key authentication enabled."""
    def override_get_db():
        try:
            yield test_db
        finally:
            test_db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Enable authentication for these tests
    original_auth = settings.ENABLE_API_KEY_AUTH
    original_keys = settings.API_KEYS
    settings.ENABLE_API_KEY_AUTH = True
    settings.API_KEYS = "test-api-key"
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Restore original settings
    settings.ENABLE_API_KEY_AUTH = original_auth
    settings.API_KEYS = original_keys
    app.dependency_overrides.clear()

@pytest.fixture
def real_client():
    """Get a TestClient for real integration tests without database override."""
    # Enable cache for real tests
    original_cache = settings.ENABLE_CACHE
    settings.ENABLE_CACHE = True
    
    # Disable authentication for easier testing
    original_auth = settings.ENABLE_API_KEY_AUTH
    settings.ENABLE_API_KEY_AUTH = False
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Restore original settings
    settings.ENABLE_CACHE = original_cache
    settings.ENABLE_API_KEY_AUTH = original_auth

@pytest.fixture
def performance_client():
    """Get a TestClient optimized for performance testing."""
    # Configure for performance testing
    original_cache = settings.ENABLE_CACHE
    original_auth = settings.ENABLE_API_KEY_AUTH
    
    settings.ENABLE_CACHE = True
    settings.ENABLE_API_KEY_AUTH = False
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Restore settings
    settings.ENABLE_CACHE = original_cache
    settings.ENABLE_API_KEY_AUTH = original_auth

@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    return {
        "title": "Software Engineer",
        "company": "Test Company",
        "location": "San Francisco, CA",
        "job_type": "fulltime",
        "description": "Test job description",
        "salary_min": 100000,
        "salary_max": 150000,
        "is_remote": False
    }

@pytest.fixture
def sample_job_search_request():
    """Sample job search request for testing."""
    return {
        "site_name": ["indeed", "linkedin"],
        "search_term": "software engineer",
        "location": "San Francisco",
        "results_wanted": 20,
        "hours_old": 72,
        "country_indeed": "USA",
        "job_type": "fulltime"
    }

@pytest.fixture
def sample_jobs_dataframe():
    """Sample pandas DataFrame with job data."""
    return pd.DataFrame({
        'SITE': ['indeed', 'linkedin', 'glassdoor'],
        'TITLE': ['Software Engineer', 'Data Scientist', 'Product Manager'],
        'COMPANY': ['Tech Corp', 'Data Inc', 'Product LLC'],
        'LOCATION': ['San Francisco, CA', 'New York, NY', 'Austin, TX'],
        'JOB_TYPE': ['fulltime', 'fulltime', 'contract'],
        'MIN_AMOUNT': [100000, 120000, 80000],
        'MAX_AMOUNT': [150000, 180000, 120000],
        'CURRENCY': ['USD', 'USD', 'USD'],
        'DESCRIPTION': ['Test description 1', 'Test description 2', 'Test description 3'],
        'DATE_POSTED': ['2024-01-01', '2024-01-02', '2024-01-03'],
        'JOB_URL': ['http://test1.com', 'http://test2.com', 'http://test3.com'],
        'EMAILS': ['', 'hr@datainc.com', ''],
        'INTERVAL': ['yearly', 'yearly', 'hourly'],
        'IS_REMOTE': [False, True, False]
    })

@pytest.fixture
def mock_jobspy_results():
    """Mock JobSpy scraping results."""
    return pd.DataFrame({
        'SITE': ['indeed'] * 5,
        'TITLE': ['Senior Software Engineer', 'Backend Developer', 'Frontend Engineer', 'Full Stack Developer', 'DevOps Engineer'],
        'COMPANY': ['TechCorp', 'StartupInc', 'BigTech', 'ScaleUp', 'CloudCorp'],
        'LOCATION': ['San Francisco, CA', 'New York, NY', 'Seattle, WA', 'Austin, TX', 'Remote'],
        'JOB_TYPE': ['fulltime'] * 5,
        'MIN_AMOUNT': [120000, 90000, 100000, 95000, 110000],
        'MAX_AMOUNT': [180000, 130000, 140000, 135000, 160000],
        'CURRENCY': ['USD'] * 5,
        'DESCRIPTION': [f'Job description {i}' for i in range(1, 6)],
        'DATE_POSTED': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05'],
        'JOB_URL': [f'http://indeed.com/job{i}' for i in range(1, 6)],
        'EMAILS': [''] * 5,
        'INTERVAL': ['yearly'] * 5,
        'IS_REMOTE': [False, False, False, False, True]
    })

@pytest.fixture
def admin_headers():
    """Headers for admin authentication."""
    return {"x-api-key": "test-admin-key"}

@pytest.fixture
def user_headers():
    """Headers for user authentication.""" 
    return {"x-api-key": "test-user-key"}

@pytest.fixture
def invalid_headers():
    """Headers with invalid API key."""
    return {"x-api-key": "invalid-key"}

@pytest.fixture
def db_with_sample_data(test_db: Session):
    """Database session with sample data."""
    # Create sample job requests
    job_request1 = JobRequest(
        search_term="software engineer",
        location="San Francisco",
        site_name="indeed",
        results_wanted=20,
        request_timestamp=datetime.utcnow(),
        status="completed"
    )
    
    job_request2 = JobRequest(
        search_term="data scientist", 
        location="New York",
        site_name="linkedin",
        results_wanted=15,
        request_timestamp=datetime.utcnow() - timedelta(hours=1),
        status="completed"
    )
    
    test_db.add(job_request1)
    test_db.add(job_request2)
    test_db.commit()
    
    # Create sample job results
    job_result1 = JobResult(
        request_id=job_request1.id,
        job_title="Senior Software Engineer",
        company_name="TechCorp",
        location="San Francisco, CA",
        job_type="fulltime",
        salary_min=120000,
        salary_max=180000,
        job_url="http://test1.com",
        description="Test job description",
        date_posted=datetime.utcnow(),
        created_at=datetime.utcnow()
    )
    
    job_result2 = JobResult(
        request_id=job_request2.id,
        job_title="Senior Data Scientist",
        company_name="DataCorp",
        location="New York, NY", 
        job_type="fulltime",
        salary_min=130000,
        salary_max=200000,
        job_url="http://test2.com",
        description="Data science role",
        date_posted=datetime.utcnow(),
        created_at=datetime.utcnow()
    )
    
    test_db.add(job_result1)
    test_db.add(job_result2) 
    test_db.commit()
    
    yield test_db
    
    # Cleanup
    test_db.query(JobResult).delete()
    test_db.query(JobRequest).delete()
    test_db.commit()

@pytest.fixture
def mock_celery_task():
    """Mock Celery task for testing."""
    task = MagicMock()
    task.delay.return_value.id = "test-task-id"
    task.delay.return_value.get.return_value = {"status": "completed"}
    return task

@pytest.fixture
def mock_redis():
    """Mock Redis client for caching tests."""
    redis_mock = MagicMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.exists.return_value = False
    return redis_mock

@pytest.fixture
def performance_test_data():
    """Large dataset for performance testing."""
    return pd.DataFrame({
        'SITE': ['indeed'] * 100,
        'TITLE': [f'Job Title {i}' for i in range(100)],
        'COMPANY': [f'Company {i}' for i in range(100)],
        'LOCATION': [f'Location {i}' for i in range(100)],
        'JOB_TYPE': ['fulltime'] * 100,
        'MIN_AMOUNT': [50000 + i * 1000 for i in range(100)],
        'MAX_AMOUNT': [80000 + i * 1000 for i in range(100)],
        'CURRENCY': ['USD'] * 100,
        'DESCRIPTION': [f'Description {i}' for i in range(100)],
        'DATE_POSTED': ['2024-01-01'] * 100,
        'JOB_URL': [f'http://test{i}.com' for i in range(100)],
        'EMAILS': [''] * 100,
        'INTERVAL': ['yearly'] * 100,
        'IS_REMOTE': [i % 2 == 0 for i in range(100)]
    })

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def anyio_backend():
    """Backend for anyio async tests."""
    return "asyncio"
