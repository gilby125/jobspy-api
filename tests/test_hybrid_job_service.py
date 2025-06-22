"""Unit tests for HybridJobService."""
import pytest
import asyncio
import pandas as pd
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any, List

from app.services.hybrid_job_service import HybridJobService
from app.workers.message_protocol import ScraperType


class TestHybridJobService:
    """Test cases for HybridJobService class."""

    @pytest.fixture
    def hybrid_service(self):
        """Create HybridJobService instance."""
        return HybridJobService()

    @pytest.fixture
    def sample_search_params(self):
        """Sample search parameters."""
        return {
            'site_name': ['indeed', 'linkedin'],
            'search_term': 'software engineer',
            'location': 'San Francisco',
            'results_wanted': 20,
            'job_type': 'fulltime'
        }

    @pytest.fixture
    def sample_go_worker_result(self):
        """Sample Go worker result format."""
        return {
            'task_id': 'test-task-123',
            'scraper_type': 'indeed',
            'status': 'completed',
            'jobs_data': [
                {
                    'title': 'Senior Software Engineer',
                    'company': 'TechCorp',
                    'location': 'San Francisco, CA',
                    'job_url': 'https://example.com/job1',
                    'description': 'Great opportunity...',
                    'salary_min': 120000,
                    'salary_max': 180000,
                    'salary_currency': 'USD',
                    'job_type': 'fulltime',
                    'is_remote': False,
                    'posted_date': '2024-01-01',
                    'easy_apply': True,
                    'apply_url': 'https://example.com/apply1',
                    'company_logo': 'https://example.com/logo1.png',
                    'skills': ['Python', 'JavaScript'],
                    'benefits': ['Health Insurance', '401k']
                },
                {
                    'title': 'Backend Developer',
                    'company': 'StartupInc',
                    'location': 'Remote',
                    'job_url': 'https://example.com/job2',
                    'description': 'Remote position...',
                    'salary_min': 90000,
                    'salary_max': 130000,
                    'salary_currency': 'USD',
                    'job_type': 'fulltime',
                    'is_remote': True,
                    'posted_date': '2024-01-02',
                    'easy_apply': False
                }
            ]
        }

    def test_init(self, hybrid_service):
        """Test HybridJobService initialization."""
        assert hybrid_service.go_worker_enabled is True
        assert hybrid_service.fallback_to_python is True
        assert hybrid_service.worker_timeout == 30
        assert 'indeed' in hybrid_service.go_supported_sites
        assert 'linkedin' in hybrid_service.python_supported_sites

    def test_route_sites_go_workers_disabled(self, hybrid_service):
        """Test site routing when Go workers are disabled."""
        hybrid_service.go_worker_enabled = False
        sites = ['indeed', 'linkedin', 'glassdoor']
        
        go_sites, python_sites = hybrid_service._route_sites(sites)
        
        assert go_sites == []
        assert python_sites == sites

    def test_route_sites_with_healthy_workers(self, hybrid_service):
        """Test site routing with healthy Go workers."""
        sites = ['indeed', 'linkedin', 'glassdoor']
        
        with patch.object(hybrid_service, '_check_go_worker_health', return_value={'indeed'}):
            go_sites, python_sites = hybrid_service._route_sites(sites)
            
            assert 'indeed' in go_sites
            assert 'linkedin' in python_sites
            assert 'glassdoor' in python_sites

    def test_route_sites_no_healthy_workers(self, hybrid_service):
        """Test site routing with no healthy Go workers."""
        sites = ['indeed', 'linkedin']
        
        with patch.object(hybrid_service, '_check_go_worker_health', return_value=set()):
            go_sites, python_sites = hybrid_service._route_sites(sites)
            
            assert go_sites == []
            assert python_sites == sites

    def test_check_go_worker_health_success(self, hybrid_service):
        """Test successful Go worker health check."""
        mock_health_statuses = [
            {'scraper_type': 'indeed', 'status': 'healthy'},
            {'scraper_type': 'linkedin', 'status': 'unhealthy'},
        ]
        
        with patch('app.services.hybrid_job_service.orchestrator') as mock_orchestrator:
            mock_orchestrator.get_scraper_health.return_value = mock_health_statuses
            
            healthy_scrapers = hybrid_service._check_go_worker_health()
            
            assert 'indeed' in healthy_scrapers
            assert 'linkedin' not in healthy_scrapers

    def test_check_go_worker_health_exception(self, hybrid_service):
        """Test Go worker health check handles exceptions."""
        with patch('app.services.hybrid_job_service.orchestrator') as mock_orchestrator:
            mock_orchestrator.get_scraper_health.side_effect = Exception("Health check failed")
            
            healthy_scrapers = hybrid_service._check_go_worker_health()
            
            assert healthy_scrapers == set()

    def test_convert_go_results_to_dataframe(self, hybrid_service, sample_go_worker_result):
        """Test conversion of Go worker results to DataFrame."""
        df = hybrid_service._convert_go_results_to_dataframe(sample_go_worker_result)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert df.iloc[0]['TITLE'] == 'Senior Software Engineer'
        assert df.iloc[0]['COMPANY'] == 'TechCorp'
        assert df.iloc[0]['MIN_AMOUNT'] == 120000
        assert df.iloc[0]['MAX_AMOUNT'] == 180000
        assert df.iloc[0]['SKILLS'] == 'Python, JavaScript'
        assert df.iloc[0]['BENEFITS'] == 'Health Insurance, 401k'
        assert df.iloc[1]['IS_REMOTE'] is True

    def test_convert_go_results_empty_data(self, hybrid_service):
        """Test conversion of empty Go worker results."""
        empty_result = {'task_id': 'test', 'jobs_data': []}
        
        df = hybrid_service._convert_go_results_to_dataframe(empty_result)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_convert_go_results_malformed_data(self, hybrid_service):
        """Test conversion handles malformed Go worker results."""
        malformed_result = {'task_id': 'test', 'jobs_data': 'not a list'}
        
        df = hybrid_service._convert_go_results_to_dataframe(malformed_result)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_deduplicate_results_url_duplicates(self, hybrid_service):
        """Test deduplication removes URL duplicates."""
        data = {
            'TITLE': ['Job 1', 'Job 1 Copy', 'Job 2'],
            'COMPANY': ['Company A', 'Company A', 'Company B'],
            'JOB_URL': ['url1', 'url1', 'url2'],  # url1 is duplicate
            'LOCATION': ['City 1', 'City 1', 'City 2']
        }
        df = pd.DataFrame(data)
        
        result = hybrid_service._deduplicate_results(df)
        
        assert len(result) == 2
        assert result['JOB_URL'].tolist() == ['url1', 'url2']

    def test_deduplicate_results_title_company_duplicates(self, hybrid_service):
        """Test deduplication removes title+company duplicates."""
        data = {
            'TITLE': ['Software Engineer', 'Software Engineer', 'Data Scientist'],
            'COMPANY': ['TechCorp', 'TechCorp', 'DataCorp'],
            'JOB_URL': ['url1', 'url2', 'url3'],  # Different URLs
            'LOCATION': ['SF', 'SF', 'NY']
        }
        df = pd.DataFrame(data)
        
        result = hybrid_service._deduplicate_results(df)
        
        assert len(result) == 2
        assert result['TITLE'].tolist() == ['Software Engineer', 'Data Scientist']

    def test_deduplicate_results_empty_dataframe(self, hybrid_service):
        """Test deduplication handles empty DataFrame."""
        df = pd.DataFrame()
        
        result = hybrid_service._deduplicate_results(df)
        
        assert len(result) == 0
        assert isinstance(result, pd.DataFrame)

    def test_generate_cache_key_consistent(self, hybrid_service):
        """Test cache key generation is consistent."""
        params1 = {'search_term': 'engineer', 'location': 'SF', 'site_name': ['indeed']}
        params2 = {'location': 'SF', 'search_term': 'engineer', 'site_name': ['indeed']}
        
        key1 = hybrid_service._generate_cache_key(params1)
        key2 = hybrid_service._generate_cache_key(params2)
        
        assert key1 == key2
        assert key1.startswith('hybrid_search:')

    def test_generate_cache_key_ignores_none_values(self, hybrid_service):
        """Test cache key generation ignores None values."""
        params_with_none = {'search_term': 'engineer', 'location': None, 'site_name': ['indeed']}
        params_without_none = {'search_term': 'engineer', 'site_name': ['indeed']}
        
        key1 = hybrid_service._generate_cache_key(params_with_none)
        key2 = hybrid_service._generate_cache_key(params_without_none)
        
        assert key1 == key2

    @pytest.mark.asyncio
    async def test_search_with_go_worker_success(self, hybrid_service, sample_go_worker_result):
        """Test successful Go worker search."""
        site = 'indeed'
        params = {'search_term': 'engineer', 'location': 'SF'}
        
        mock_task = MagicMock()
        mock_task.task_id = 'test-task-123'
        
        with patch('app.services.hybrid_job_service.orchestrator') as mock_orchestrator:
            mock_orchestrator.create_scraping_task.return_value = mock_task
            mock_orchestrator.submit_scraping_task.return_value = True
            mock_orchestrator.process_scraping_results.return_value = sample_go_worker_result
            
            result = await hybrid_service._search_with_go_worker(site, params)
            
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_search_with_go_worker_submit_failure(self, hybrid_service):
        """Test Go worker search when task submission fails."""
        site = 'indeed'
        params = {'search_term': 'engineer'}
        
        mock_task = MagicMock()
        
        with patch('app.services.hybrid_job_service.orchestrator') as mock_orchestrator:
            mock_orchestrator.create_scraping_task.return_value = mock_task
            mock_orchestrator.submit_scraping_task.return_value = False
            
            result = await hybrid_service._search_with_go_worker(site, params)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_search_with_go_worker_timeout(self, hybrid_service):
        """Test Go worker search timeout."""
        site = 'indeed'
        params = {'search_term': 'engineer'}
        hybrid_service.worker_timeout = 0.1  # Very short timeout for testing
        
        mock_task = MagicMock()
        mock_task.task_id = 'test-task-123'
        
        with patch('app.services.hybrid_job_service.orchestrator') as mock_orchestrator:
            mock_orchestrator.create_scraping_task.return_value = mock_task
            mock_orchestrator.submit_scraping_task.return_value = True
            mock_orchestrator.process_scraping_results.return_value = None  # No results
            
            result = await hybrid_service._search_with_go_worker(site, params)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_search_with_go_worker_exception(self, hybrid_service):
        """Test Go worker search handles exceptions."""
        site = 'indeed'
        params = {'search_term': 'engineer'}
        
        with patch('app.services.hybrid_job_service.orchestrator') as mock_orchestrator:
            mock_orchestrator.create_scraping_task.side_effect = Exception("Worker error")
            
            result = await hybrid_service._search_with_go_worker(site, params)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_search_with_python_jobspy_success(self, hybrid_service, sample_jobs_dataframe):
        """Test successful Python JobSpy search."""
        sites = ['linkedin', 'glassdoor']
        params = {'search_term': 'engineer', 'location': 'SF'}
        
        with patch('app.services.hybrid_job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (sample_jobs_dataframe, False)
            
            result = await hybrid_service._search_with_python_jobspy(sites, params)
            
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 3
            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_python_jobspy_exception(self, hybrid_service):
        """Test Python JobSpy search handles exceptions."""
        sites = ['linkedin']
        params = {'search_term': 'engineer'}
        
        with patch('app.services.hybrid_job_service.JobService.search_jobs', side_effect=Exception("JobSpy error")):
            result = await hybrid_service._search_with_python_jobspy(sites, params)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_search_jobs_cached_result(self, hybrid_service, sample_search_params, sample_jobs_dataframe):
        """Test search_jobs returns cached result."""
        with patch('app.services.hybrid_job_service.cache') as mock_cache, \
             patch('app.services.hybrid_job_service.settings') as mock_settings:
            
            mock_settings.ENABLE_CACHE = True
            mock_cache.get.return_value = sample_jobs_dataframe
            
            result_df, is_cached = await hybrid_service.search_jobs(sample_search_params)
            
            assert is_cached is True
            assert isinstance(result_df, pd.DataFrame)
            assert len(result_df) == 3

    @pytest.mark.asyncio
    async def test_search_jobs_no_cache(self, hybrid_service, sample_search_params, sample_jobs_dataframe):
        """Test search_jobs when cache is disabled."""
        with patch('app.services.hybrid_job_service.cache') as mock_cache, \
             patch('app.services.hybrid_job_service.settings') as mock_settings, \
             patch.object(hybrid_service, '_route_sites', return_value=([], ['linkedin'])), \
             patch.object(hybrid_service, '_search_with_python_jobspy', return_value=sample_jobs_dataframe):
            
            mock_settings.ENABLE_CACHE = False
            mock_cache.get.return_value = None
            
            result_df, is_cached = await hybrid_service.search_jobs(sample_search_params)
            
            assert is_cached is False
            assert isinstance(result_df, pd.DataFrame)
            mock_cache.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_jobs_mixed_workers(self, hybrid_service, sample_search_params):
        """Test search_jobs with both Go workers and Python JobSpy."""
        go_df = pd.DataFrame({
            'TITLE': ['Go Job 1'],
            'COMPANY': ['Go Company'],
            'JOB_URL': ['go_url_1'],
            'LOCATION': ['SF']
        })
        
        python_df = pd.DataFrame({
            'TITLE': ['Python Job 1'],
            'COMPANY': ['Python Company'],
            'JOB_URL': ['python_url_1'],
            'LOCATION': ['NY']
        })
        
        with patch('app.services.hybrid_job_service.cache') as mock_cache, \
             patch('app.services.hybrid_job_service.settings') as mock_settings, \
             patch.object(hybrid_service, '_route_sites', return_value=(['indeed'], ['linkedin'])), \
             patch.object(hybrid_service, '_search_with_go_worker', return_value=go_df), \
             patch.object(hybrid_service, '_search_with_python_jobspy', return_value=python_df):
            
            mock_settings.ENABLE_CACHE = False
            mock_cache.get.return_value = None
            
            result_df, is_cached = await hybrid_service.search_jobs(sample_search_params)
            
            assert is_cached is False
            assert isinstance(result_df, pd.DataFrame)
            assert len(result_df) == 2
            assert 'Go Job 1' in result_df['TITLE'].values
            assert 'Python Job 1' in result_df['TITLE'].values

    @pytest.mark.asyncio
    async def test_search_jobs_go_worker_fallback(self, hybrid_service, sample_search_params, sample_jobs_dataframe):
        """Test search_jobs with Go worker failure and Python fallback."""
        with patch('app.services.hybrid_job_service.cache') as mock_cache, \
             patch('app.services.hybrid_job_service.settings') as mock_settings, \
             patch.object(hybrid_service, '_route_sites', return_value=(['indeed'], [])), \
             patch.object(hybrid_service, '_search_with_go_worker', side_effect=Exception("Go worker failed")), \
             patch.object(hybrid_service, '_search_with_python_jobspy', return_value=sample_jobs_dataframe):
            
            mock_settings.ENABLE_CACHE = False
            mock_cache.get.return_value = None
            hybrid_service.fallback_to_python = True
            
            result_df, is_cached = await hybrid_service.search_jobs(sample_search_params)
            
            assert is_cached is False
            assert isinstance(result_df, pd.DataFrame)
            assert len(result_df) == 3  # From fallback to Python

    @pytest.mark.asyncio
    async def test_search_jobs_no_results(self, hybrid_service, sample_search_params):
        """Test search_jobs when no results are found."""
        with patch('app.services.hybrid_job_service.cache') as mock_cache, \
             patch('app.services.hybrid_job_service.settings') as mock_settings, \
             patch.object(hybrid_service, '_route_sites', return_value=([], ['linkedin'])), \
             patch.object(hybrid_service, '_search_with_python_jobspy', return_value=None):
            
            mock_settings.ENABLE_CACHE = False
            mock_cache.get.return_value = None
            
            result_df, is_cached = await hybrid_service.search_jobs(sample_search_params)
            
            assert is_cached is False
            assert isinstance(result_df, pd.DataFrame)
            assert len(result_df) == 0

    @pytest.mark.asyncio
    async def test_search_jobs_string_site_name(self, hybrid_service, sample_jobs_dataframe):
        """Test search_jobs handles string site_name parameter."""
        params = {
            'site_name': 'indeed',  # String instead of list
            'search_term': 'engineer'
        }
        
        with patch('app.services.hybrid_job_service.cache') as mock_cache, \
             patch('app.services.hybrid_job_service.settings') as mock_settings, \
             patch.object(hybrid_service, '_route_sites', return_value=([], ['indeed'])), \
             patch.object(hybrid_service, '_search_with_python_jobspy', return_value=sample_jobs_dataframe):
            
            mock_settings.ENABLE_CACHE = False
            mock_cache.get.return_value = None
            
            result_df, is_cached = await hybrid_service.search_jobs(params)
            
            assert is_cached is False
            assert isinstance(result_df, pd.DataFrame)

    @pytest.mark.asyncio
    async def test_get_scraper_status_success(self, hybrid_service):
        """Test successful scraper status retrieval."""
        mock_go_health = [
            {'scraper_type': 'indeed', 'status': 'healthy'}
        ]
        mock_queue_status = {'pending_tasks': 5, 'active_workers': 3}
        
        with patch('app.services.hybrid_job_service.orchestrator') as mock_orchestrator, \
             patch('builtins.__import__'):  # Mock jobspy import
            
            mock_orchestrator.get_scraper_health.return_value = mock_go_health
            mock_orchestrator.get_queue_status.return_value = mock_queue_status
            
            status = await hybrid_service.get_scraper_status()
            
            assert 'go_workers' in status
            assert 'python_jobspy' in status
            assert 'routing' in status
            assert 'timestamp' in status
            assert status['go_workers']['enabled'] is True
            assert status['python_jobspy']['available'] is True

    @pytest.mark.asyncio
    async def test_get_scraper_status_import_error(self, hybrid_service):
        """Test scraper status when JobSpy import fails."""
        with patch('app.services.hybrid_job_service.orchestrator') as mock_orchestrator, \
             patch('builtins.__import__', side_effect=ImportError("No module named 'jobspy'")):
            
            mock_orchestrator.get_scraper_health.return_value = []
            mock_orchestrator.get_queue_status.return_value = {}
            
            status = await hybrid_service.get_scraper_status()
            
            assert status['python_jobspy']['available'] is False

    @pytest.mark.asyncio
    async def test_get_scraper_status_exception(self, hybrid_service):
        """Test scraper status handles exceptions."""
        with patch('app.services.hybrid_job_service.orchestrator') as mock_orchestrator:
            mock_orchestrator.get_scraper_health.side_effect = Exception("Orchestrator error")
            
            status = await hybrid_service.get_scraper_status()
            
            assert 'error' in status

    @pytest.mark.asyncio
    async def test_search_jobs_with_caching_enabled(self, hybrid_service, sample_search_params, sample_jobs_dataframe):
        """Test search_jobs caches results when caching is enabled."""
        with patch('app.services.hybrid_job_service.cache') as mock_cache, \
             patch('app.services.hybrid_job_service.settings') as mock_settings, \
             patch.object(hybrid_service, '_route_sites', return_value=([], ['linkedin'])), \
             patch.object(hybrid_service, '_search_with_python_jobspy', return_value=sample_jobs_dataframe):
            
            mock_settings.ENABLE_CACHE = True
            mock_settings.CACHE_EXPIRY = 3600
            mock_cache.get.return_value = None  # No cached result
            mock_cache.set = AsyncMock()
            
            result_df, is_cached = await hybrid_service.search_jobs(sample_search_params)
            
            assert is_cached is False
            mock_cache.set.assert_called_once()

    def test_route_sites_case_insensitive(self, hybrid_service):
        """Test site routing is case insensitive for Go workers."""
        sites = ['INDEED', 'LinkedIn']
        
        with patch.object(hybrid_service, '_check_go_worker_health', return_value={'indeed'}):
            go_sites, python_sites = hybrid_service._route_sites(sites)
            
            assert 'indeed' in go_sites  # Should be lowercased
            assert 'LinkedIn' in python_sites  # Original case preserved for Python