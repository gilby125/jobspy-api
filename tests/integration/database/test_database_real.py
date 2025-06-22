"""Real database integration tests."""
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta

from app.models.tracking_models import (
    Company, JobPosting, Location, JobCategory, 
    JobSource, JobMetrics, ScrapingRun
)
from app.db.database import get_db, engine, check_database_connection
from tests.fixtures.sample_data import SAMPLE_COMPANIES, SAMPLE_LOCATIONS


class TestDatabaseRealIntegration:
    """Test database operations with real data persistence."""

    def test_database_connection_real(self):
        """Test real database connection."""
        assert check_database_connection() is True

    def test_create_company_real(self, test_db: Session):
        """Test creating a real company record."""
        company_data = SAMPLE_COMPANIES[0].copy()
        
        company = Company(
            name=company_data["name"],
            domain=company_data["domain"],
            industry=company_data["industry"],
            company_size=company_data["company_size"],
            headquarters_location=company_data["headquarters_location"],
            description=company_data["description"]
        )
        
        test_db.add(company)
        test_db.commit()
        test_db.refresh(company)
        
        assert company.id is not None
        assert company.name == company_data["name"]
        assert company.created_at is not None

    def test_create_location_real(self, test_db: Session):
        """Test creating a real location record."""
        location_data = SAMPLE_LOCATIONS[0].copy()
        
        location = Location(
            city=location_data["city"],
            state=location_data["state"],
            country=location_data["country"],
            region=location_data["region"]
        )
        
        test_db.add(location)
        test_db.commit()
        test_db.refresh(location)
        
        assert location.id is not None
        assert location.city == location_data["city"]
        assert location.created_at is not None

    def test_create_job_category_real(self, test_db: Session):
        """Test creating a real job category."""
        category = JobCategory(name="Software Development")
        
        test_db.add(category)
        test_db.commit()
        test_db.refresh(category)
        
        assert category.id is not None
        assert category.name == "Software Development"

    def test_create_job_posting_real(self, test_db: Session):
        """Test creating a complete job posting with relationships."""
        # Create required related objects first
        company = Company(name="Test Company", domain="test.com")
        test_db.add(company)
        test_db.commit()
        test_db.refresh(company)
        
        location = Location(city="Test City", state="Test State", country="USA")
        test_db.add(location)
        test_db.commit()
        test_db.refresh(location)
        
        category = JobCategory(name="Engineering")
        test_db.add(category)
        test_db.commit()
        test_db.refresh(category)
        
        # Create job posting
        job_posting = JobPosting(
            job_hash="test_hash_123",
            title="Senior Software Engineer",
            company_id=company.id,
            location_id=location.id,
            job_category_id=category.id,
            job_type="fulltime",
            experience_level="senior",
            is_remote=False,
            description="Test job description",
            requirements="Python, FastAPI",
            salary_min=100000,
            salary_max=150000,
            salary_currency="USD",
            salary_interval="yearly",
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
            status="active"
        )
        
        test_db.add(job_posting)
        test_db.commit()
        test_db.refresh(job_posting)
        
        assert job_posting.id is not None
        assert job_posting.title == "Senior Software Engineer"
        assert job_posting.company.name == "Test Company"
        assert job_posting.location.city == "Test City"
        assert job_posting.job_category.name == "Engineering"

    def test_create_job_source_real(self, test_db: Session):
        """Test creating job sources with real data."""
        # Create job posting first
        company = Company(name="Source Test Company")
        test_db.add(company)
        test_db.commit()
        
        job_posting = JobPosting(
            job_hash="source_test_hash",
            title="Test Job",
            company_id=company.id,
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow()
        )
        test_db.add(job_posting)
        test_db.commit()
        test_db.refresh(job_posting)
        
        # Create job source
        job_source = JobSource(
            job_posting_id=job_posting.id,
            source_site="indeed",
            external_job_id="indeed_123",
            job_url="https://indeed.com/job/123",
            post_date=datetime.utcnow().date(),
            apply_url="https://indeed.com/apply/123",
            easy_apply=False
        )
        
        test_db.add(job_source)
        test_db.commit()
        test_db.refresh(job_source)
        
        assert job_source.id is not None
        assert job_source.source_site == "indeed"
        assert job_source.job_posting.title == "Test Job"

    def test_create_job_metrics_real(self, test_db: Session):
        """Test creating job metrics with real data."""
        # Create job posting first
        company = Company(name="Metrics Test Company")
        test_db.add(company)
        test_db.commit()
        
        job_posting = JobPosting(
            job_hash="metrics_test_hash",
            title="Metrics Test Job",
            company_id=company.id,
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow()
        )
        test_db.add(job_posting)
        test_db.commit()
        test_db.refresh(job_posting)
        
        # Create job metrics
        job_metrics = JobMetrics(
            job_posting_id=job_posting.id,
            total_seen_count=5,
            sites_posted_count=2,
            days_active=7,
            repost_count=1,
            last_activity_date=datetime.utcnow().date()
        )
        
        test_db.add(job_metrics)
        test_db.commit()
        test_db.refresh(job_metrics)
        
        assert job_metrics.id is not None
        assert job_metrics.total_seen_count == 5
        assert job_metrics.job_posting.title == "Metrics Test Job"

    def test_create_scraping_run_real(self, test_db: Session):
        """Test creating scraping run records."""
        scraping_run = ScrapingRun(
            source_site="indeed",
            search_params={"search_term": "python", "location": "SF"},
            status="completed",
            jobs_found=25,
            jobs_new=5,
            jobs_updated=3,
            started_at=datetime.utcnow() - timedelta(minutes=10),
            completed_at=datetime.utcnow(),
            worker_id="worker_123"
        )
        
        test_db.add(scraping_run)
        test_db.commit()
        test_db.refresh(scraping_run)
        
        assert scraping_run.id is not None
        assert scraping_run.source_site == "indeed"
        assert scraping_run.status == "completed"
        assert scraping_run.jobs_found == 25

    def test_job_deduplication_real(self, test_db: Session):
        """Test job deduplication with same hash."""
        company = Company(name="Dedup Test Company")
        test_db.add(company)
        test_db.commit()
        
        # Try to create two jobs with same hash
        job1 = JobPosting(
            job_hash="duplicate_hash_123",
            title="Duplicate Job",
            company_id=company.id,
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow()
        )
        test_db.add(job1)
        test_db.commit()
        
        job2 = JobPosting(
            job_hash="duplicate_hash_123",  # Same hash
            title="Another Duplicate Job",
            company_id=company.id,
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow()
        )
        
        # This should fail due to unique constraint
        test_db.add(job2)
        with pytest.raises(Exception):  # Should raise integrity error
            test_db.commit()

    def test_complex_query_real(self, test_db: Session):
        """Test complex database queries with real data."""
        # Create test data
        company1 = Company(name="Query Test Company 1", industry="Technology")
        company2 = Company(name="Query Test Company 2", industry="Finance")
        test_db.add_all([company1, company2])
        test_db.commit()
        
        location = Location(city="Query City", state="QS", country="USA")
        test_db.add(location)
        test_db.commit()
        
        # Create multiple job postings
        jobs = [
            JobPosting(
                job_hash="query_hash_1",
                title="Senior Python Developer",
                company_id=company1.id,
                location_id=location.id,
                job_type="fulltime",
                salary_min=120000,
                salary_max=180000,
                first_seen_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
                status="active"
            ),
            JobPosting(
                job_hash="query_hash_2",
                title="Junior Java Developer",
                company_id=company2.id,
                location_id=location.id,
                job_type="fulltime",
                salary_min=80000,
                salary_max=120000,
                first_seen_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
                status="active"
            )
        ]
        test_db.add_all(jobs)
        test_db.commit()
        
        # Test complex query
        result = test_db.query(JobPosting).join(Company).filter(
            Company.industry == "Technology",
            JobPosting.salary_min >= 100000
        ).all()
        
        assert len(result) == 1
        assert result[0].title == "Senior Python Developer"

    def test_raw_sql_query_real(self, test_db: Session):
        """Test raw SQL queries with real database."""
        # Test a simple raw query
        result = test_db.execute(text("SELECT 1 as test_value"))
        row = result.fetchone()
        assert row[0] == 1

    def test_database_transaction_rollback_real(self, test_db: Session):
        """Test transaction rollback with real data."""
        company = Company(name="Rollback Test Company")
        test_db.add(company)
        test_db.flush()  # Flush to get ID but don't commit
        
        company_id = company.id
        assert company_id is not None
        
        # Rollback the transaction
        test_db.rollback()
        
        # Company should not exist after rollback
        found_company = test_db.query(Company).filter(Company.id == company_id).first()
        assert found_company is None

    def test_database_constraints_real(self, test_db: Session):
        """Test database constraints with real data."""
        # Test NOT NULL constraint
        with pytest.raises(Exception):
            job = JobPosting(
                job_hash=None,  # This should fail
                title="Test Job"
            )
            test_db.add(job)
            test_db.commit()

    def test_database_relationships_real(self, test_db: Session):
        """Test database relationships with real data."""
        # Create company with multiple jobs
        company = Company(name="Relationship Test Company")
        test_db.add(company)
        test_db.commit()
        
        jobs = [
            JobPosting(
                job_hash=f"rel_hash_{i}",
                title=f"Job {i}",
                company_id=company.id,
                first_seen_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow()
            )
            for i in range(3)
        ]
        test_db.add_all(jobs)
        test_db.commit()
        
        # Test relationship access
        test_db.refresh(company)
        assert len(company.job_postings) == 3
        
        # Test reverse relationship
        job = jobs[0]
        test_db.refresh(job)
        assert job.company.name == "Relationship Test Company"