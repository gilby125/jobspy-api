"""Unit tests for JobService."""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any

from app.services.job_service import JobService
from app.core.config import settings
from app.cache import cache


class TestJobService:
    """Test cases for JobService class."""

    @pytest.mark.asyncio
    async def test_search_jobs_with_defaults(self, sample_jobs_dataframe):
        """Test search_jobs applies default settings correctly."""
        params = {
            'site_name': ['indeed'],
            'search_term': 'software engineer',
            'location': 'San Francisco'
        }
        
        with patch('app.services.job_service.scrape_jobs') as mock_scrape, \
             patch.object(cache, 'get', return_value=None), \
             patch.object(cache, 'set') as mock_cache_set:
            
            mock_scrape.return_value = sample_jobs_dataframe
            
            # Mock settings
            settings.default_proxies_list = ['proxy1.com', 'proxy2.com']
            settings.CA_CERT_PATH = '/path/to/cert'
            settings.DEFAULT_COUNTRY_INDEED = 'USA'
            
            result_df, is_cached = await JobService.search_jobs(params)
            
            # Verify defaults were applied
            mock_scrape.assert_called_once()
            call_args = mock_scrape.call_args[1]
            assert call_args['proxies'] == ['proxy1.com', 'proxy2.com']
            assert call_args['ca_cert'] == '/path/to/cert'
            assert call_args['country_indeed'] == 'USA'
            
            # Verify result
            assert isinstance(result_df, pd.DataFrame)
            assert not is_cached
            assert len(result_df) == 3
            
            # Verify caching was called
            mock_cache_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_jobs_cached_results(self, sample_jobs_dataframe):
        """Test search_jobs returns cached results when available."""
        params = {
            'site_name': ['indeed'],
            'search_term': 'python developer'
        }
        
        with patch.object(cache, 'get', return_value=sample_jobs_dataframe), \
             patch('app.services.job_service.scrape_jobs') as mock_scrape:
            
            result_df, is_cached = await JobService.search_jobs(params)
            
            # Verify cached result was returned
            assert is_cached
            assert isinstance(result_df, pd.DataFrame)
            assert len(result_df) == 3
            
            # Verify scrape_jobs was not called
            mock_scrape.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_jobs_preserves_user_params(self, sample_jobs_dataframe):
        """Test search_jobs doesn't override user-provided parameters."""
        params = {
            'site_name': ['linkedin'],
            'search_term': 'data scientist',
            'proxies': ['user-proxy.com'],
            'ca_cert': '/user/cert/path',
            'country_indeed': 'UK'
        }
        
        with patch('app.services.job_service.scrape_jobs') as mock_scrape, \
             patch.object(cache, 'get', return_value=None), \
             patch.object(cache, 'set'):
            
            mock_scrape.return_value = sample_jobs_dataframe
            
            await JobService.search_jobs(params)
            
            # Verify user params were preserved
            call_args = mock_scrape.call_args[1]
            assert call_args['proxies'] == ['user-proxy.com']
            assert call_args['ca_cert'] == '/user/cert/path'
            assert call_args['country_indeed'] == 'UK'

    @pytest.mark.asyncio
    async def test_search_jobs_error_handling(self):
        """Test search_jobs handles errors from scrape_jobs."""
        params = {'site_name': ['indeed'], 'search_term': 'test'}
        
        with patch('app.services.job_service.scrape_jobs') as mock_scrape, \
             patch.object(cache, 'get', return_value=None):
            
            mock_scrape.side_effect = Exception("Scraping failed")
            
            with pytest.raises(Exception, match="Scraping failed"):
                await JobService.search_jobs(params)

    def test_filter_jobs_by_salary_range(self, sample_jobs_dataframe):
        """Test filtering jobs by salary range."""
        filters = {
            'min_salary': 110000,
            'max_salary': 160000
        }
        
        result = JobService.filter_jobs(sample_jobs_dataframe, filters)
        
        # Should return only Data Scientist job (120k-180k)
        assert len(result) == 1
        assert result.iloc[0]['TITLE'] == 'Data Scientist'
        assert result.iloc[0]['MIN_AMOUNT'] == 120000
        assert result.iloc[0]['MAX_AMOUNT'] == 180000

    def test_filter_jobs_by_company(self, sample_jobs_dataframe):
        """Test filtering jobs by company name."""
        filters = {'company': 'Data'}
        
        result = JobService.filter_jobs(sample_jobs_dataframe, filters)
        
        # Should return only Data Inc job
        assert len(result) == 1
        assert result.iloc[0]['COMPANY'] == 'Data Inc'

    def test_filter_jobs_by_job_type(self, sample_jobs_dataframe):
        """Test filtering jobs by job type."""
        filters = {'job_type': 'contract'}
        
        result = JobService.filter_jobs(sample_jobs_dataframe, filters)
        
        # Should return only contract job
        assert len(result) == 1
        assert result.iloc[0]['JOB_TYPE'] == 'contract'
        assert result.iloc[0]['TITLE'] == 'Product Manager'

    def test_filter_jobs_by_title_keywords(self, sample_jobs_dataframe):
        """Test filtering jobs by title keywords."""
        filters = {'title_keywords': 'Engineer'}
        
        result = JobService.filter_jobs(sample_jobs_dataframe, filters)
        
        # Should return only Software Engineer job
        assert len(result) == 1
        assert result.iloc[0]['TITLE'] == 'Software Engineer'

    def test_filter_jobs_multiple_criteria(self, sample_jobs_dataframe):
        """Test filtering jobs with multiple criteria."""
        filters = {
            'job_type': 'fulltime',
            'min_salary': 110000,
            'company': 'Data'
        }
        
        result = JobService.filter_jobs(sample_jobs_dataframe, filters)
        
        # Should return only Data Scientist job (fulltime, salary >= 110k, company contains 'Data')
        assert len(result) == 1
        assert result.iloc[0]['TITLE'] == 'Data Scientist'

    def test_filter_jobs_no_matches(self, sample_jobs_dataframe):
        """Test filtering jobs with criteria that match no jobs."""
        filters = {'min_salary': 200000}  # No jobs have min salary >= 200k
        
        result = JobService.filter_jobs(sample_jobs_dataframe, filters)
        
        assert len(result) == 0

    def test_filter_jobs_empty_filters(self, sample_jobs_dataframe):
        """Test filtering jobs with empty filters returns all jobs."""
        filters = {}
        
        result = JobService.filter_jobs(sample_jobs_dataframe, filters)
        
        assert len(result) == 3
        assert result.equals(sample_jobs_dataframe)

    def test_filter_jobs_none_values(self, sample_jobs_dataframe):
        """Test filtering jobs with None filter values."""
        filters = {
            'min_salary': None,
            'max_salary': None,
            'company': None,
            'job_type': None
        }
        
        result = JobService.filter_jobs(sample_jobs_dataframe, filters)
        
        # Should return all jobs since None values are ignored
        assert len(result) == 3

    def test_sort_jobs_by_salary_desc(self, sample_jobs_dataframe):
        """Test sorting jobs by salary in descending order."""
        result = JobService.sort_jobs(sample_jobs_dataframe, 'MIN_AMOUNT', 'desc')
        
        # Should be sorted by MIN_AMOUNT descending: Data Scientist (120k), Software Engineer (100k), Product Manager (80k)
        assert result.iloc[0]['TITLE'] == 'Data Scientist'
        assert result.iloc[1]['TITLE'] == 'Software Engineer'
        assert result.iloc[2]['TITLE'] == 'Product Manager'

    def test_sort_jobs_by_salary_asc(self, sample_jobs_dataframe):
        """Test sorting jobs by salary in ascending order."""
        result = JobService.sort_jobs(sample_jobs_dataframe, 'MIN_AMOUNT', 'asc')
        
        # Should be sorted by MIN_AMOUNT ascending: Product Manager (80k), Software Engineer (100k), Data Scientist (120k)
        assert result.iloc[0]['TITLE'] == 'Product Manager'
        assert result.iloc[1]['TITLE'] == 'Software Engineer'
        assert result.iloc[2]['TITLE'] == 'Data Scientist'

    def test_sort_jobs_by_company(self, sample_jobs_dataframe):
        """Test sorting jobs by company name."""
        result = JobService.sort_jobs(sample_jobs_dataframe, 'COMPANY', 'asc')
        
        # Should be sorted alphabetically by company
        companies = result['COMPANY'].tolist()
        assert companies == sorted(companies)

    def test_sort_jobs_invalid_column(self, sample_jobs_dataframe):
        """Test sorting jobs by invalid column returns original dataframe."""
        result = JobService.sort_jobs(sample_jobs_dataframe, 'INVALID_COLUMN')
        
        # Should return original dataframe unchanged
        assert result.equals(sample_jobs_dataframe)

    def test_sort_jobs_empty_sort_by(self, sample_jobs_dataframe):
        """Test sorting jobs with empty sort_by returns original dataframe."""
        result = JobService.sort_jobs(sample_jobs_dataframe, '')
        
        # Should return original dataframe unchanged
        assert result.equals(sample_jobs_dataframe)

    def test_sort_jobs_none_sort_by(self, sample_jobs_dataframe):
        """Test sorting jobs with None sort_by returns original dataframe."""
        result = JobService.sort_jobs(sample_jobs_dataframe, None)
        
        # Should return original dataframe unchanged
        assert result.equals(sample_jobs_dataframe)

    def test_sort_jobs_default_order(self, sample_jobs_dataframe):
        """Test sorting jobs with default order (desc)."""
        result = JobService.sort_jobs(sample_jobs_dataframe, 'MIN_AMOUNT')
        
        # Default should be descending
        assert result.iloc[0]['MIN_AMOUNT'] >= result.iloc[1]['MIN_AMOUNT']
        assert result.iloc[1]['MIN_AMOUNT'] >= result.iloc[2]['MIN_AMOUNT']

    def test_filter_jobs_preserves_original(self, sample_jobs_dataframe):
        """Test that filtering doesn't modify the original dataframe."""
        original_len = len(sample_jobs_dataframe)
        filters = {'min_salary': 110000}
        
        result = JobService.filter_jobs(sample_jobs_dataframe, filters)
        
        # Original dataframe should be unchanged
        assert len(sample_jobs_dataframe) == original_len
        assert len(result) < original_len

    def test_sort_jobs_preserves_original(self, sample_jobs_dataframe):
        """Test that sorting doesn't modify the original dataframe."""
        original_first_title = sample_jobs_dataframe.iloc[0]['TITLE']
        
        result = JobService.sort_jobs(sample_jobs_dataframe, 'TITLE', 'desc')
        
        # Original dataframe should be unchanged
        assert sample_jobs_dataframe.iloc[0]['TITLE'] == original_first_title
        # Result should be different (unless coincidentally the same)
        if len(sample_jobs_dataframe) > 1:
            # Only test if we have multiple items to potentially reorder
            pass  # This test just ensures no in-place modification occurred

    @pytest.mark.asyncio
    async def test_search_jobs_with_empty_params(self):
        """Test search_jobs with minimal parameters."""
        params = {}
        
        with patch('app.services.job_service.scrape_jobs') as mock_scrape, \
             patch.object(cache, 'get', return_value=None), \
             patch.object(cache, 'set'):
            
            mock_scrape.return_value = pd.DataFrame()
            
            result_df, is_cached = await JobService.search_jobs(params)
            
            assert isinstance(result_df, pd.DataFrame)
            assert not is_cached
            mock_scrape.assert_called_once()

    def test_filter_jobs_with_location_filters(self):
        """Test filtering jobs by city and state (if columns exist)."""
        # Create test data with city and state columns
        df_with_location = pd.DataFrame({
            'TITLE': ['Job 1', 'Job 2', 'Job 3'],
            'COMPANY': ['Co 1', 'Co 2', 'Co 3'],
            'CITY': ['San Francisco', 'New York', 'Austin'],
            'STATE': ['CA', 'NY', 'TX'],
            'JOB_TYPE': ['fulltime'] * 3,
            'MIN_AMOUNT': [100000] * 3,
            'MAX_AMOUNT': [150000] * 3
        })
        
        # Test city filter
        city_filters = {'city': 'Francisco'}
        result = JobService.filter_jobs(df_with_location, city_filters)
        assert len(result) == 1
        assert result.iloc[0]['CITY'] == 'San Francisco'
        
        # Test state filter  
        state_filters = {'state': 'NY'}
        result = JobService.filter_jobs(df_with_location, state_filters)
        assert len(result) == 1
        assert result.iloc[0]['STATE'] == 'NY'

    def test_filter_jobs_case_insensitive(self, sample_jobs_dataframe):
        """Test that string filters are case insensitive."""
        filters = {'company': 'data'}  # lowercase
        
        result = JobService.filter_jobs(sample_jobs_dataframe, filters)
        
        # Should still match 'Data Inc'
        assert len(result) == 1
        assert result.iloc[0]['COMPANY'] == 'Data Inc'

    def test_filter_jobs_handles_na_values(self):
        """Test that filtering handles NaN values properly."""
        df_with_na = pd.DataFrame({
            'TITLE': ['Job 1', 'Job 2'],
            'COMPANY': ['Company 1', None],
            'JOB_TYPE': ['fulltime', 'fulltime'],
            'MIN_AMOUNT': [100000, 120000],
            'MAX_AMOUNT': [150000, 180000]
        })
        
        filters = {'company': 'Company'}
        result = JobService.filter_jobs(df_with_na, filters)
        
        # Should only return the job with non-null company that matches
        assert len(result) == 1
        assert result.iloc[0]['COMPANY'] == 'Company 1'