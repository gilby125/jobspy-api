"""Unit tests for JobTrackingService."""
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.services.job_tracking_service import JobTrackingService
from app.models.tracking_models import (
    JobPosting, Company, Location, JobCategory, JobSource, 
    JobMetrics, ScrapingRun
)


class TestJobTrackingService:
    """Test cases for JobTrackingService class."""

    @pytest.fixture
    def job_tracking_service(self):
        """Create JobTrackingService instance."""
        return JobTrackingService()

    @pytest.fixture
    def sample_job_data(self):
        """Sample job data for testing."""
        return {
            'title': 'Senior Software Engineer',
            'company': 'TechCorp Inc',
            'location': 'San Francisco, CA, USA',
            'job_type': 'fulltime',
            'description': 'We are looking for a senior software engineer with experience in Python and JavaScript. Requirements: 5+ years experience, Bachelor\'s degree.',
            'min_amount': 120000,
            'max_amount': 180000,
            'currency': 'USD',
            'interval': 'yearly',
            'job_url': 'https://example.com/job1',
            'job_url_direct': 'https://example.com/apply1',
            'date_posted': '2024-01-01',
            'easy_apply': True,
            'job_id': 'ext_job_123',
            'company_logo': 'https://example.com/logo.png',
            'company_description': 'Leading tech company'
        }

    @pytest.fixture
    def sample_jobs_list(self, sample_job_data):
        """Sample list of job data."""
        return [
            sample_job_data,
            {
                **sample_job_data,
                'title': 'Backend Developer',
                'company': 'StartupInc',
                'location': 'Remote',
                'min_amount': 90000,
                'max_amount': 130000,
                'job_url': 'https://example.com/job2',
                'job_id': 'ext_job_124'
            },
            {
                **sample_job_data,
                'title': 'Frontend Engineer', 
                'company': 'BigCorp',
                'location': 'New York, NY, USA',
                'min_amount': 100000,
                'max_amount': 150000,
                'job_url': 'https://example.com/job3',
                'job_id': 'ext_job_125'
            }
        ]

    def test_init(self, job_tracking_service):
        """Test JobTrackingService initialization."""
        assert job_tracking_service.dedup_service is not None

    def test_process_scraped_jobs_success(self, job_tracking_service, sample_jobs_list, test_db):
        """Test successful processing of scraped jobs."""
        search_params = {'search_term': 'engineer', 'location': 'SF'}
        
        with patch.object(job_tracking_service, '_process_single_job') as mock_process:
            # Mock single job processing
            mock_process.side_effect = [
                {
                    'action': 'created',
                    'job_posting': MagicMock(id=1, title='Job 1', company=MagicMock(name='Company 1')),
                    'new_company': True
                },
                {
                    'action': 'merged',
                    'job_posting': MagicMock(id=2, title='Job 2', company=MagicMock(name='Company 2')),
                    'similarity_score': 0.95
                },
                {
                    'action': 'updated',
                    'job_posting': MagicMock(id=3, title='Job 3', company=MagicMock(name='Company 3'))
                }
            ]
            
            stats = job_tracking_service.process_scraped_jobs(
                sample_jobs_list, 'indeed', search_params, test_db
            )
            
            assert stats['total_jobs'] == 3
            assert stats['new_jobs'] == 1
            assert stats['duplicate_jobs'] == 1
            assert stats['updated_jobs'] == 1
            assert stats['errors'] == 0
            assert stats['new_companies'] == 1
            assert len(stats['processed_jobs']) == 3

    def test_process_scraped_jobs_with_errors(self, job_tracking_service, sample_jobs_list, test_db):
        """Test processing scraped jobs with some errors."""
        search_params = {'search_term': 'engineer'}
        
        with patch.object(job_tracking_service, '_process_single_job') as mock_process:
            # Mock with one error
            mock_process.side_effect = [
                {
                    'action': 'created',
                    'job_posting': MagicMock(id=1, title='Job 1', company=MagicMock(name='Company 1'))
                },
                Exception("Processing error"),
                {
                    'action': 'merged',
                    'job_posting': MagicMock(id=3, title='Job 3', company=MagicMock(name='Company 3'))
                }
            ]
            
            stats = job_tracking_service.process_scraped_jobs(
                sample_jobs_list, 'linkedin', search_params, test_db
            )
            
            assert stats['total_jobs'] == 3
            assert stats['new_jobs'] == 1
            assert stats['duplicate_jobs'] == 1
            assert stats['errors'] == 1
            assert len(stats['processed_jobs']) == 2

    def test_process_single_job_duplicate(self, job_tracking_service, sample_job_data, test_db):
        """Test processing a duplicate job."""
        existing_job = MagicMock()
        existing_job.id = 123
        
        with patch.object(job_tracking_service.dedup_service, 'is_duplicate_job', return_value=(True, existing_job)), \
             patch.object(job_tracking_service.dedup_service, 'merge_job_sources', return_value=existing_job):
            
            result = job_tracking_service._process_single_job(sample_job_data, 'indeed', test_db)
            
            assert result['action'] == 'merged'
            assert result['job_posting'] == existing_job
            assert result['similarity_score'] == 1.0

    def test_process_single_job_new(self, job_tracking_service, sample_job_data, test_db):
        """Test processing a new job."""
        new_job = MagicMock()
        new_job.id = 456
        new_job.company_id = 789
        
        with patch.object(job_tracking_service.dedup_service, 'is_duplicate_job', return_value=(False, None)), \
             patch.object(job_tracking_service, '_create_new_job_posting', return_value=new_job):
            
            result = job_tracking_service._process_single_job(sample_job_data, 'linkedin', test_db)
            
            assert result['action'] == 'created'
            assert result['job_posting'] == new_job
            assert result['new_company'] == 789

    def test_create_new_job_posting(self, job_tracking_service, sample_job_data, test_db):
        """Test creating a new job posting."""
        mock_company = MagicMock()
        mock_company.id = 1
        mock_company.name = 'TechCorp Inc'
        
        mock_location = MagicMock()
        mock_location.id = 2
        
        mock_category = MagicMock()
        mock_category.id = 3
        
        with patch.object(job_tracking_service, '_get_or_create_company', return_value=mock_company), \
             patch.object(job_tracking_service, '_get_or_create_location', return_value=mock_location), \
             patch.object(job_tracking_service, '_get_or_create_job_category', return_value=mock_category), \
             patch.object(job_tracking_service.dedup_service, 'generate_job_hash', return_value='test_hash'), \
             patch.object(test_db, 'add'), \
             patch.object(test_db, 'flush'), \
             patch.object(test_db, 'commit'):
            
            with patch('app.services.job_tracking_service.JobPosting') as mock_job_posting_class, \
                 patch('app.services.job_tracking_service.JobSource') as mock_job_source_class, \
                 patch('app.services.job_tracking_service.JobMetrics') as mock_job_metrics_class:
                
                mock_job_posting = MagicMock()
                mock_job_posting.id = 100
                mock_job_posting_class.return_value = mock_job_posting
                
                result = job_tracking_service._create_new_job_posting(sample_job_data, 'indeed', test_db)
                
                assert result == mock_job_posting
                mock_job_posting_class.assert_called_once()
                mock_job_source_class.assert_called_once()
                mock_job_metrics_class.assert_called_once()

    def test_get_or_create_company_existing(self, job_tracking_service, sample_job_data, test_db):
        """Test getting existing company."""
        existing_company = MagicMock()
        existing_company.name = 'TechCorp Inc'
        
        with patch.object(test_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = existing_company
            
            result = job_tracking_service._get_or_create_company(sample_job_data, test_db)
            
            assert result == existing_company

    def test_get_or_create_company_new(self, job_tracking_service, sample_job_data, test_db):
        """Test creating new company."""
        with patch.object(test_db, 'query') as mock_query, \
             patch.object(test_db, 'add'), \
             patch.object(test_db, 'flush'), \
             patch.object(job_tracking_service, '_extract_industry', return_value='Technology'):
            
            mock_query.return_value.filter.return_value.first.return_value = None
            
            with patch('app.services.job_tracking_service.Company') as mock_company_class:
                mock_company = MagicMock()
                mock_company_class.return_value = mock_company
                
                result = job_tracking_service._get_or_create_company(sample_job_data, test_db)
                
                assert result == mock_company
                mock_company_class.assert_called_once()

    def test_get_or_create_company_no_name(self, job_tracking_service, test_db):
        """Test creating company with no name provided."""
        job_data_no_company = {'title': 'Test Job'}
        
        with patch.object(test_db, 'query') as mock_query, \
             patch.object(test_db, 'add'), \
             patch.object(test_db, 'flush'):
            
            mock_query.return_value.filter.return_value.first.return_value = None
            
            with patch('app.services.job_tracking_service.Company') as mock_company_class:
                mock_company = MagicMock()
                mock_company_class.return_value = mock_company
                
                result = job_tracking_service._get_or_create_company(job_data_no_company, test_db)
                
                # Should create company with "Unknown Company" name
                assert result == mock_company

    def test_get_or_create_location_existing(self, job_tracking_service, sample_job_data, test_db):
        """Test getting existing location."""
        existing_location = MagicMock()
        
        with patch.object(test_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = existing_location
            
            result = job_tracking_service._get_or_create_location(sample_job_data, test_db)
            
            assert result == existing_location

    def test_get_or_create_location_remote(self, job_tracking_service, test_db):
        """Test location handling for remote jobs."""
        job_data_remote = {'location': 'Remote'}
        
        result = job_tracking_service._get_or_create_location(job_data_remote, test_db)
        
        assert result is None

    def test_get_or_create_location_new(self, job_tracking_service, sample_job_data, test_db):
        """Test creating new location."""
        with patch.object(test_db, 'query') as mock_query, \
             patch.object(test_db, 'add'), \
             patch.object(test_db, 'flush'), \
             patch.object(job_tracking_service, '_get_region_for_country', return_value='North America'):
            
            mock_query.return_value.filter.return_value.first.return_value = None
            
            with patch('app.services.job_tracking_service.Location') as mock_location_class:
                mock_location = MagicMock()
                mock_location_class.return_value = mock_location
                
                result = job_tracking_service._get_or_create_location(sample_job_data, test_db)
                
                assert result == mock_location
                mock_location_class.assert_called_once()

    def test_get_or_create_job_category_existing(self, job_tracking_service, sample_job_data, test_db):
        """Test getting existing job category."""
        existing_category = MagicMock()
        
        with patch.object(test_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = existing_category
            
            result = job_tracking_service._get_or_create_job_category(sample_job_data, test_db)
            
            assert result == existing_category

    def test_get_or_create_job_category_new(self, job_tracking_service, sample_job_data, test_db):
        """Test creating new job category."""
        with patch.object(test_db, 'query') as mock_query, \
             patch.object(test_db, 'add'), \
             patch.object(test_db, 'flush'):
            
            mock_query.return_value.filter.return_value.first.return_value = None
            
            with patch('app.services.job_tracking_service.JobCategory') as mock_category_class:
                mock_category = MagicMock()
                mock_category_class.return_value = mock_category
                
                result = job_tracking_service._get_or_create_job_category(sample_job_data, test_db)
                
                assert result == mock_category
                mock_category_class.assert_called_once()

    def test_get_job_analytics(self, job_tracking_service, test_db):
        """Test getting job analytics."""
        with patch.object(test_db, 'query') as mock_query:
            # Mock the query chain for different analytics
            mock_query_result = MagicMock()
            mock_query_result.count.return_value = 100
            mock_query.return_value = mock_query_result
            mock_query_result.filter.return_value = mock_query_result
            
            # Mock top companies query
            mock_companies = [('TechCorp', 25), ('StartupInc', 15)]
            
            # Mock job types query
            mock_job_types = [('fulltime', 80), ('contract', 20)]
            
            # Mock salary stats
            mock_salary_stats = MagicMock()
            mock_salary_stats.avg_min_salary = 90000
            mock_salary_stats.avg_max_salary = 140000
            mock_salary_stats.salary_count = 75
            
            with patch.multiple(test_db, 
                              query=MagicMock(side_effect=[
                                  mock_query_result,  # total jobs
                                  mock_query_result,  # active jobs
                                  MagicMock(join=MagicMock(return_value=MagicMock(
                                      filter=MagicMock(return_value=MagicMock(
                                          group_by=MagicMock(return_value=MagicMock(
                                              order_by=MagicMock(return_value=MagicMock(
                                                  limit=MagicMock(return_value=MagicMock(
                                                      all=MagicMock(return_value=mock_companies)
                                                  ))
                                              ))
                                          ))
                                      ))
                                  ))),  # top companies
                                  MagicMock(filter=MagicMock(return_value=MagicMock(
                                      group_by=MagicMock(return_value=MagicMock(
                                          all=MagicMock(return_value=mock_job_types)
                                      ))
                                  ))),  # job types
                                  MagicMock(filter=MagicMock(return_value=MagicMock(
                                      first=MagicMock(return_value=mock_salary_stats)
                                  )))  # salary stats
                              ])):
                
                analytics = job_tracking_service.get_job_analytics(test_db, days_back=30)
                
                assert analytics['total_jobs'] == 100
                assert analytics['active_jobs'] == 100
                assert len(analytics['top_companies']) == 2
                assert analytics['top_companies'][0]['name'] == 'TechCorp'
                assert len(analytics['job_type_distribution']) == 2
                assert analytics['salary_trends']['avg_min_salary'] == 90000.0

    def test_extract_experience_level(self, job_tracking_service):
        """Test experience level extraction from job titles."""
        assert job_tracking_service._extract_experience_level('Senior Software Engineer') == 'senior'
        assert job_tracking_service._extract_experience_level('Junior Developer') == 'entry'
        assert job_tracking_service._extract_experience_level('Engineering Manager') == 'executive'
        assert job_tracking_service._extract_experience_level('Software Developer') == 'mid'
        assert job_tracking_service._extract_experience_level('Lead Engineer') == 'senior'
        assert job_tracking_service._extract_experience_level('Director of Engineering') == 'executive'

    def test_extract_requirements(self, job_tracking_service):
        """Test requirements extraction from job descriptions."""
        description = "We are hiring. Requirements: 5+ years experience, Python skills. Benefits include health insurance."
        
        requirements = job_tracking_service._extract_requirements(description)
        
        assert 'Requirements:' in requirements
        assert '5+ years experience' in requirements

    def test_extract_requirements_no_section(self, job_tracking_service):
        """Test requirements extraction when no requirements section found."""
        description = "We are hiring for a great position with competitive salary."
        
        requirements = job_tracking_service._extract_requirements(description)
        
        assert requirements == ""

    def test_parse_salary_valid(self, job_tracking_service):
        """Test parsing valid salary amounts."""
        assert job_tracking_service._parse_salary(100000) == 100000.0
        assert job_tracking_service._parse_salary('$120,000') == 120000.0
        assert job_tracking_service._parse_salary('85000') == 85000.0
        assert job_tracking_service._parse_salary(75000.5) == 75000.5

    def test_parse_salary_invalid(self, job_tracking_service):
        """Test parsing invalid salary amounts."""
        assert job_tracking_service._parse_salary(None) is None
        assert job_tracking_service._parse_salary('') is None
        assert job_tracking_service._parse_salary('not a number') is None
        assert job_tracking_service._parse_salary([]) is None

    def test_parse_location_components(self, job_tracking_service):
        """Test parsing location components."""
        city, state, country = job_tracking_service._parse_location_components('San Francisco, CA, USA')
        assert city == 'San Francisco'
        assert state == 'CA'
        assert country == 'USA'
        
        city, state, country = job_tracking_service._parse_location_components('New York, NY')
        assert city == 'New York'
        assert state == 'NY'
        assert country == 'USA'  # Default
        
        city, state, country = job_tracking_service._parse_location_components('London')
        assert city == 'London'
        assert state == ''
        assert country == 'USA'  # Default

    def test_get_region_for_country(self, job_tracking_service):
        """Test getting region for countries."""
        assert job_tracking_service._get_region_for_country('USA') == 'North America'
        assert job_tracking_service._get_region_for_country('UK') == 'Europe'
        assert job_tracking_service._get_region_for_country('INDIA') == 'Asia'
        assert job_tracking_service._get_region_for_country('UNKNOWN') == 'Other'

    def test_extract_industry(self, job_tracking_service):
        """Test industry extraction from job descriptions."""
        tech_desc = "We are a leading software company building cloud solutions with AI and machine learning."
        assert job_tracking_service._extract_industry(tech_desc) == 'Technology'
        
        healthcare_desc = "Join our healthcare team at a major hospital providing medical services."
        assert job_tracking_service._extract_industry(healthcare_desc) == 'Healthcare'
        
        finance_desc = "Work at our fintech startup in the finance and banking sector."
        assert job_tracking_service._extract_industry(finance_desc) == 'Finance'
        
        generic_desc = "Great opportunity for career growth."
        assert job_tracking_service._extract_industry(generic_desc) is None

    def test_parse_date_delegation(self, job_tracking_service):
        """Test that date parsing is delegated to deduplication service."""
        with patch.object(job_tracking_service.dedup_service, '_parse_date', return_value=date(2024, 1, 1)) as mock_parse:
            result = job_tracking_service._parse_date('2024-01-01')
            
            mock_parse.assert_called_once_with('2024-01-01')
            assert result == date(2024, 1, 1)