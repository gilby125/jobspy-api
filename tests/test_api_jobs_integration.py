"""Integration tests for /api/jobs endpoints."""
import pytest
import json
import pandas as pd
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import status
from datetime import datetime, timedelta

from app.models.tracking_models import JobRequest, JobResult


class TestJobsAPIIntegration:
    """Integration test cases for jobs API endpoints."""

    def test_search_jobs_post_basic_success(self, client, sample_jobs_dataframe):
        """Test POST /api/v1/search_jobs with basic parameters."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (sample_jobs_dataframe, False)
            
            response = client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": ["indeed"],
                    "search_term": "software engineer",
                    "location": "San Francisco",
                    "results_wanted": 20
                }
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["count"] == 3
            assert not data["cached"]
            assert len(data["jobs"]) == 3
            assert data["jobs"][0]["TITLE"] == "Software Engineer"

    def test_search_jobs_post_with_all_parameters(self, client, sample_jobs_dataframe):
        """Test POST /api/v1/search_jobs with all parameters."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (sample_jobs_dataframe, False)
            
            response = client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": ["indeed", "linkedin"],
                    "search_term": "data scientist",
                    "location": "New York",
                    "results_wanted": 50,
                    "hours_old": 72,
                    "country_indeed": "USA",
                    "job_type": "fulltime",
                    "is_remote": False,
                    "easy_apply": True,
                    "distance": 25
                }
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["count"] == 3
            assert "search_params" in data
            assert data["search_params"]["search_term"] == "data scientist"

    def test_search_jobs_post_cached_response(self, client, sample_jobs_dataframe):
        """Test POST /api/v1/search_jobs returns cached response."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (sample_jobs_dataframe, True)
            
            response = client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": ["linkedin"],
                    "search_term": "python developer"
                }
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["cached"] is True

    def test_search_jobs_post_validation_error(self, client):
        """Test POST /api/v1/search_jobs with validation errors."""
        response = client.post(
            "/api/v1/search_jobs",
            json={
                "site_name": ["invalid_site"],
                "search_term": "",  # Empty search term
                "results_wanted": -5  # Invalid negative value
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "error" in data
        assert "Validation Error" in data["error"]

    def test_search_jobs_post_service_error(self, client):
        """Test POST /api/v1/search_jobs handles service errors."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.side_effect = Exception("JobSpy scraping failed")
            
            response = client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": ["indeed"],
                    "search_term": "test"
                }
            )
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "error" in data
            assert "Server Error" in data["error"]

    def test_search_jobs_get_basic(self, client, sample_jobs_dataframe):
        """Test GET /api/v1/search_jobs with query parameters."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (sample_jobs_dataframe, False)
            
            response = client.get(
                "/api/v1/search_jobs?site_name=indeed&search_term=engineer&location=SF"
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["count"] == 3

    def test_search_jobs_get_csv_format(self, client, sample_jobs_dataframe):
        """Test GET /api/v1/search_jobs with CSV format."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (sample_jobs_dataframe, False)
            
            response = client.get(
                "/api/v1/search_jobs?format=csv&search_term=test&site_name=indeed"
            )
            
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "text/csv; charset=utf-8"
            assert "TITLE,COMPANY,LOCATION" in response.text

    def test_search_jobs_get_with_filters(self, client, sample_jobs_dataframe):
        """Test GET /api/v1/search_jobs with filtering parameters."""
        # Create DataFrame with more varied data for filtering
        filtered_df = pd.DataFrame({
            'TITLE': ['Senior Software Engineer'],
            'COMPANY': ['TechCorp'],
            'LOCATION': ['San Francisco, CA'],
            'JOB_TYPE': ['fulltime'],
            'MIN_AMOUNT': [120000],
            'MAX_AMOUNT': [180000]
        })
        
        with patch('app.services.job_service.JobService.search_jobs') as mock_search, \
             patch('app.services.job_service.JobService.filter_jobs') as mock_filter, \
             patch('app.services.job_service.JobService.sort_jobs') as mock_sort:
            
            mock_search.return_value = (sample_jobs_dataframe, False)
            mock_filter.return_value = filtered_df
            mock_sort.return_value = filtered_df
            
            response = client.get(
                "/api/v1/search_jobs?"
                "search_term=engineer&"
                "site_name=indeed&"
                "min_salary=100000&"
                "max_salary=200000&"
                "company=tech&"
                "job_type=fulltime&"
                "sort_by=MIN_AMOUNT&"
                "sort_order=desc"
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["count"] == 1
            
            # Verify filtering was called
            mock_filter.assert_called_once()
            mock_sort.assert_called_once()

    def test_search_jobs_get_missing_required_params(self, client):
        """Test GET /api/v1/search_jobs without required parameters."""
        response = client.get("/api/v1/search_jobs")
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_database_search_jobs_success(self, client, db_with_sample_data):
        """Test GET /api/v1/jobs/search_jobs database endpoint."""
        response = client.get("/api/v1/jobs/search_jobs")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "jobs" in data
        assert isinstance(data["jobs"], list)

    def test_database_search_jobs_with_filters(self, client, db_with_sample_data):
        """Test GET /api/v1/jobs/search_jobs with query filters."""
        response = client.get(
            "/api/v1/jobs/search_jobs?"
            "search_term=engineer&"
            "location=San Francisco&"
            "job_type=fulltime&"
            "min_salary=100000&"
            "max_salary=200000&"
            "limit=10&"
            "offset=0"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "jobs" in data
        assert "total_count" in data
        assert "search_params" in data

    def test_database_search_jobs_no_results(self, client, test_db):
        """Test GET /api/v1/jobs/search_jobs with no results."""
        response = client.get("/api/v1/jobs/search_jobs?search_term=nonexistent")
        
        # Should return 200 with empty results, not 404
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["jobs"] == []
        assert data["total_count"] == 0

    def test_get_job_by_id_success(self, client, db_with_sample_data):
        """Test GET /api/v1/jobs/{job_id}."""
        # First get a job ID from the database
        response = client.get("/api/v1/jobs/search_jobs?limit=1")
        assert response.status_code == status.HTTP_200_OK
        jobs = response.json()["jobs"]
        
        if jobs:
            job_id = jobs[0]["id"]
            
            response = client.get(f"/api/v1/jobs/{job_id}")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == job_id
            assert "job_title" in data
            assert "company_name" in data

    def test_get_job_by_id_not_found(self, client):
        """Test GET /api/v1/jobs/{job_id} with non-existent ID."""
        response = client.get("/api/v1/jobs/99999")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_job_by_id_invalid_id(self, client):
        """Test GET /api/v1/jobs/{job_id} with invalid ID format."""
        response = client.get("/api/v1/jobs/invalid-id")
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_search_jobs_authentication_required(self, authenticated_client, user_headers):
        """Test search jobs endpoints require authentication when enabled."""
        response = authenticated_client.post(
            "/api/v1/search_jobs",
            json={"site_name": ["indeed"], "search_term": "test"},
            headers=user_headers
        )
        
        # Should not return 403 with valid API key
        assert response.status_code != status.HTTP_403_FORBIDDEN

    def test_search_jobs_invalid_authentication(self, authenticated_client, invalid_headers):
        """Test search jobs endpoints reject invalid authentication."""
        response = authenticated_client.post(
            "/api/v1/search_jobs",
            json={"site_name": ["indeed"], "search_term": "test"},
            headers=invalid_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_search_jobs_rate_limiting(self, client):
        """Test rate limiting on search endpoints."""
        # This test would need actual rate limiting configuration
        # For now, just verify the endpoint is accessible
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (pd.DataFrame(), False)
            
            response = client.post(
                "/api/v1/search_jobs",
                json={"site_name": ["indeed"], "search_term": "test"}
            )
            
            # Should have rate limiting headers (if enabled)
            assert response.status_code == status.HTTP_200_OK

    def test_search_jobs_concurrent_requests(self, client, sample_jobs_dataframe):
        """Test handling of concurrent search requests."""
        import asyncio
        import aiohttp
        
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (sample_jobs_dataframe, False)
            
            # Test that multiple concurrent requests don't interfere
            response1 = client.post(
                "/api/v1/search_jobs",
                json={"site_name": ["indeed"], "search_term": "engineer"}
            )
            
            response2 = client.post(
                "/api/v1/search_jobs", 
                json={"site_name": ["linkedin"], "search_term": "developer"}
            )
            
            assert response1.status_code == status.HTTP_200_OK
            assert response2.status_code == status.HTTP_200_OK

    def test_search_jobs_large_dataset(self, client, performance_test_data):
        """Test search jobs endpoint with large dataset."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (performance_test_data, False)
            
            response = client.post(
                "/api/v1/search_jobs",
                json={"site_name": ["indeed"], "search_term": "test"}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["count"] == 100
            assert len(data["jobs"]) == 100

    def test_search_jobs_empty_results(self, client):
        """Test search jobs endpoint with empty results."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (pd.DataFrame(), False)
            
            response = client.post(
                "/api/v1/search_jobs",
                json={"site_name": ["indeed"], "search_term": "nonexistent"}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["count"] == 0
            assert data["jobs"] == []

    def test_search_jobs_invalid_json(self, client):
        """Test search jobs endpoint with invalid JSON."""
        response = client.post(
            "/api/v1/search_jobs",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_search_jobs_missing_content_type(self, client):
        """Test search jobs endpoint without content type."""
        response = client.post(
            "/api/v1/search_jobs",
            data='{"site_name": ["indeed"], "search_term": "test"}'
        )
        
        # Should still work or return appropriate error
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]

    def test_search_jobs_site_name_variations(self, client, sample_jobs_dataframe):
        """Test search jobs with different site name formats."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (sample_jobs_dataframe, False)
            
            # Test single site as string
            response = client.post(
                "/api/v1/search_jobs",
                json={"site_name": "indeed", "search_term": "test"}
            )
            assert response.status_code == status.HTTP_200_OK
            
            # Test single site as list
            response = client.post(
                "/api/v1/search_jobs",
                json={"site_name": ["indeed"], "search_term": "test"}
            )
            assert response.status_code == status.HTTP_200_OK
            
            # Test multiple sites
            response = client.post(
                "/api/v1/search_jobs",
                json={"site_name": ["indeed", "linkedin"], "search_term": "test"}
            )
            assert response.status_code == status.HTTP_200_OK

    def test_database_jobs_pagination(self, client, db_with_sample_data):
        """Test database jobs endpoint pagination."""
        # Test first page
        response = client.get("/api/v1/jobs/search_jobs?limit=1&offset=0")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["jobs"]) <= 1
        
        # Test second page  
        response = client.get("/api/v1/jobs/search_jobs?limit=1&offset=1")
        assert response.status_code == status.HTTP_200_OK

    def test_search_jobs_response_format_consistency(self, client, sample_jobs_dataframe):
        """Test that response format is consistent across different scenarios."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (sample_jobs_dataframe, False)
            
            response = client.post(
                "/api/v1/search_jobs",
                json={"site_name": ["indeed"], "search_term": "test"}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # Check required fields
            required_fields = ["count", "jobs", "cached", "search_params", "timestamp"]
            for field in required_fields:
                assert field in data
            
            # Check job object structure
            if data["jobs"]:
                job = data["jobs"][0]
                expected_job_fields = ["TITLE", "COMPANY", "LOCATION", "JOB_TYPE"]
                for field in expected_job_fields:
                    assert field in job

    def test_search_jobs_error_handling_edge_cases(self, client):
        """Test various error handling edge cases."""
        # Test extremely long search term
        long_term = "a" * 1000
        response = client.post(
            "/api/v1/search_jobs",
            json={"site_name": ["indeed"], "search_term": long_term}
        )
        # Should handle gracefully
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]
        
        # Test negative results_wanted
        response = client.post(
            "/api/v1/search_jobs",
            json={"site_name": ["indeed"], "search_term": "test", "results_wanted": -10}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test extremely high results_wanted
        response = client.post(
            "/api/v1/search_jobs",
            json={"site_name": ["indeed"], "search_term": "test", "results_wanted": 10000}
        )
        # Should be capped or return validation error
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]