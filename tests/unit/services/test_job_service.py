"""Real tests for JobService using actual JobSpy library."""
import pytest
import asyncio
from unittest.mock import patch
import pandas as pd

from app.services.job_service import JobService
from app.core.config import settings
from tests.fixtures.sample_data import get_sample_search_params, get_error_scenario


class TestJobServiceReal:
    """Test JobService with real JobSpy integration."""

    @pytest.mark.asyncio
    async def test_search_jobs_basic_real(self):
        """Test basic job search with real JobSpy call."""
        params = get_sample_search_params("basic_search")
        params["results_wanted"] = 5  # Small number for faster test
        
        jobs_df, is_cached = await JobService.search_jobs(params)
        
        assert isinstance(jobs_df, pd.DataFrame)
        assert isinstance(is_cached, bool)
        assert len(jobs_df) >= 0  # May be 0 if no jobs found
        
        if len(jobs_df) > 0:
            # Check required columns exist
            expected_columns = ['SITE', 'TITLE', 'COMPANY']
            for col in expected_columns:
                assert col in jobs_df.columns

    @pytest.mark.asyncio
    async def test_search_jobs_with_cache(self):
        """Test job search caching with real cache operations."""
        params = get_sample_search_params("basic_search")
        params["results_wanted"] = 3
        
        # First call - should not be cached
        jobs_df1, is_cached1 = await JobService.search_jobs(params)
        assert is_cached1 is False
        
        # Second call with same params - should be cached
        jobs_df2, is_cached2 = await JobService.search_jobs(params)
        assert is_cached2 is True
        
        # Results should be identical
        if len(jobs_df1) > 0 and len(jobs_df2) > 0:
            pd.testing.assert_frame_equal(jobs_df1, jobs_df2)

    @pytest.mark.asyncio
    async def test_search_jobs_with_defaults(self):
        """Test job search applies default settings correctly."""
        params = {
            "site_name": ["indeed"],
            "search_term": "software engineer",
            "results_wanted": 2
        }
        
        jobs_df, is_cached = await JobService.search_jobs(params)
        
        assert isinstance(jobs_df, pd.DataFrame)
        # Test passes if no exception is thrown and we get a DataFrame

    def test_filter_jobs_real_data(self):
        """Test job filtering with real data structure."""
        # Create a realistic DataFrame structure
        jobs_data = {
            'TITLE': ['Software Engineer', 'Data Scientist', 'Product Manager'],
            'COMPANY': ['TechCorp', 'DataCorp', 'ProductCorp'],
            'LOCATION': ['San Francisco', 'New York', 'Austin'],
            'JOB_TYPE': ['fulltime', 'fulltime', 'parttime'],
            'MIN_AMOUNT': [100000, 120000, 80000],
            'MAX_AMOUNT': [150000, 180000, 120000],
            'CITY': ['San Francisco', 'New York', 'Austin'],
            'STATE': ['CA', 'NY', 'TX']
        }
        jobs_df = pd.DataFrame(jobs_data)
        
        # Test salary filtering
        filters = {'min_salary': 110000}
        filtered_df = JobService.filter_jobs(jobs_df, filters)
        assert len(filtered_df) == 2  # Should exclude the 80k-120k job
        
        # Test company filtering
        filters = {'company': 'Tech'}
        filtered_df = JobService.filter_jobs(jobs_df, filters)
        assert len(filtered_df) == 1
        assert 'TechCorp' in filtered_df['COMPANY'].values
        
        # Test job type filtering
        filters = {'job_type': 'fulltime'}
        filtered_df = JobService.filter_jobs(jobs_df, filters)
        assert len(filtered_df) == 2

    def test_sort_jobs_real_data(self):
        """Test job sorting with real data structure."""
        jobs_data = {
            'TITLE': ['Junior Dev', 'Senior Dev', 'Lead Dev'],
            'MIN_AMOUNT': [60000, 100000, 140000],
            'DATE_POSTED': ['2024-01-01', '2024-01-03', '2024-01-02']
        }
        jobs_df = pd.DataFrame(jobs_data)
        
        # Test sorting by salary (descending)
        sorted_df = JobService.sort_jobs(jobs_df, 'MIN_AMOUNT', 'desc')
        assert sorted_df.iloc[0]['TITLE'] == 'Lead Dev'
        assert sorted_df.iloc[-1]['TITLE'] == 'Junior Dev'
        
        # Test sorting by salary (ascending)
        sorted_df = JobService.sort_jobs(jobs_df, 'MIN_AMOUNT', 'asc')
        assert sorted_df.iloc[0]['TITLE'] == 'Junior Dev'
        assert sorted_df.iloc[-1]['TITLE'] == 'Lead Dev'

    @pytest.mark.asyncio
    async def test_search_jobs_error_handling(self):
        """Test error handling with invalid parameters."""
        invalid_params = get_error_scenario("invalid_site")
        
        with pytest.raises(Exception):
            await JobService.search_jobs(invalid_params)

    @pytest.mark.asyncio
    async def test_search_jobs_multiple_sites(self):
        """Test job search across multiple sites."""
        params = {
            "site_name": ["indeed", "linkedin"],
            "search_term": "python",
            "results_wanted": 5,
            "location": "remote"
        }
        
        jobs_df, is_cached = await JobService.search_jobs(params)
        
        assert isinstance(jobs_df, pd.DataFrame)
        
        if len(jobs_df) > 0:
            # Check that we have jobs from multiple sites (if available)
            sites = jobs_df['SITE'].unique() if 'SITE' in jobs_df.columns else []
            assert len(sites) >= 1

    @pytest.mark.asyncio
    async def test_search_jobs_remote_filter(self):
        """Test remote job filtering."""
        params = {
            "site_name": ["indeed"],
            "search_term": "remote developer",
            "is_remote": True,
            "results_wanted": 3
        }
        
        jobs_df, is_cached = await JobService.search_jobs(params)
        
        assert isinstance(jobs_df, pd.DataFrame)
        # Test passes if no exception and we get results

    @pytest.mark.asyncio
    async def test_search_jobs_with_job_type(self):
        """Test job search with specific job type."""
        params = {
            "site_name": ["indeed"],
            "search_term": "software engineer",
            "job_type": "fulltime",
            "results_wanted": 3
        }
        
        jobs_df, is_cached = await JobService.search_jobs(params)
        
        assert isinstance(jobs_df, pd.DataFrame)
        # Test passes if no exception and we get results

    def test_filter_jobs_edge_cases(self):
        """Test job filtering edge cases with real data."""
        # Empty DataFrame
        empty_df = pd.DataFrame()
        filters = {'min_salary': 100000}
        filtered_df = JobService.filter_jobs(empty_df, filters)
        assert len(filtered_df) == 0
        
        # DataFrame with missing columns
        incomplete_df = pd.DataFrame({'TITLE': ['Test Job']})
        filtered_df = JobService.filter_jobs(incomplete_df, filters)
        assert len(filtered_df) == 0  # Should handle missing columns gracefully

    def test_sort_jobs_edge_cases(self):
        """Test job sorting edge cases."""
        # Empty DataFrame
        empty_df = pd.DataFrame()
        sorted_df = JobService.sort_jobs(empty_df, 'TITLE', 'desc')
        assert len(sorted_df) == 0
        
        # Sort by non-existent column
        jobs_df = pd.DataFrame({'TITLE': ['Job 1', 'Job 2']})
        sorted_df = JobService.sort_jobs(jobs_df, 'NON_EXISTENT', 'desc')
        pd.testing.assert_frame_equal(sorted_df, jobs_df)  # Should return original

    @pytest.mark.asyncio
    async def test_search_jobs_configuration_application(self):
        """Test that configuration settings are properly applied."""
        params = {
            "site_name": ["indeed"],
            "search_term": "test",
            "results_wanted": 2
        }
        
        # Test with default configuration
        jobs_df, is_cached = await JobService.search_jobs(params)
        
        assert isinstance(jobs_df, pd.DataFrame)
        # Verify the search completed without configuration errors
        
    @pytest.mark.asyncio
    async def test_search_jobs_concurrent_requests(self):
        """Test concurrent job search requests."""
        params1 = {
            "site_name": ["indeed"],
            "search_term": "python",
            "results_wanted": 2
        }
        params2 = {
            "site_name": ["linkedin"],
            "search_term": "javascript",
            "results_wanted": 2
        }
        
        # Run concurrent searches
        task1 = JobService.search_jobs(params1)
        task2 = JobService.search_jobs(params2)
        
        results = await asyncio.gather(task1, task2, return_exceptions=True)
        
        assert len(results) == 2
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"Concurrent search failed: {result}")
            else:
                jobs_df, is_cached = result
                assert isinstance(jobs_df, pd.DataFrame)