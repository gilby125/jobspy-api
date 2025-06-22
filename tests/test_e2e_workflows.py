"""End-to-end workflow tests for JobSpy API."""
import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import status
from datetime import datetime, timedelta


class TestEndToEndWorkflows:
    """End-to-end test cases covering complete user workflows."""

    def test_complete_job_search_workflow(self, client, sample_jobs_dataframe):
        """Test complete job search workflow from request to response."""
        # 1. Check API health
        health_response = client.get("/health")
        assert health_response.status_code == status.HTTP_200_OK
        
        # 2. Perform job search
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (sample_jobs_dataframe, False)
            
            search_response = client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": ["indeed", "linkedin"],
                    "search_term": "python developer",
                    "location": "San Francisco",
                    "results_wanted": 20,
                    "job_type": "fulltime"
                }
            )
            
            assert search_response.status_code == status.HTTP_200_OK
            search_data = search_response.json()
            assert search_data["count"] > 0
            assert len(search_data["jobs"]) > 0
            
        # 3. Verify search results structure
        jobs = search_data["jobs"]
        first_job = jobs[0]
        required_fields = ["TITLE", "COMPANY", "LOCATION", "JOB_TYPE"]
        for field in required_fields:
            assert field in first_job
            
        # 4. Test cached search (second identical request)
        with patch('app.services.job_service.JobService.search_jobs') as mock_search_cached:
            mock_search_cached.return_value = (sample_jobs_dataframe, True)
            
            cached_response = client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": ["indeed", "linkedin"],
                    "search_term": "python developer", 
                    "location": "San Francisco",
                    "results_wanted": 20,
                    "job_type": "fulltime"
                }
            )
            
            assert cached_response.status_code == status.HTTP_200_OK
            cached_data = cached_response.json()
            assert cached_data["cached"] is True

    def test_admin_scheduled_search_workflow(self, client):
        """Test complete admin workflow for scheduled searches."""
        # 1. Check admin dashboard
        mock_stats = {
            "total_searches": 100,
            "searches_today": 15,
            "total_jobs_found": 2500,
            "jobs_found_today": 150,
            "active_searches": 2,
            "failed_searches_today": 1,
            "cache_hit_rate": 0.75,
            "system_health": {"api": "healthy", "database": "healthy"}
        }
        
        with patch('app.services.admin_service.AdminService.get_admin_stats', new_callable=AsyncMock) as mock_get_stats:
            mock_get_stats.return_value = MagicMock(**mock_stats)
            
            dashboard_response = client.get("/admin/dashboard")
            assert dashboard_response.status_code == status.HTTP_200_OK
            dashboard_data = dashboard_response.json()
            assert dashboard_data["total_searches"] == 100
        
        # 2. Create a search template
        template_data = {
            "name": "Python Developer Template",
            "description": "Template for Python developer searches",
            "search_term": "python developer",
            "location": "San Francisco",
            "site_names": ["indeed", "linkedin"],
            "job_type": "fulltime",
            "results_wanted": 25
        }
        
        mock_template_response = {
            "id": "template-123",
            **template_data,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        with patch('app.services.admin_service.AdminService.create_search_template', new_callable=AsyncMock) as mock_create_template:
            mock_create_template.return_value = mock_template_response
            
            template_response = client.post("/admin/search-templates", json=template_data)
            assert template_response.status_code == status.HTTP_201_CREATED
            template_id = template_response.json()["id"]
        
        # 3. Create scheduled search using template
        search_request = {
            "name": "Nightly Python Developer Search",
            "search_term": "python developer",
            "location": "San Francisco",
            "site_names": ["indeed", "linkedin"],
            "job_type": "fulltime",
            "results_wanted": 25,
            "schedule_time": (datetime.now() + timedelta(hours=1)).isoformat(),
            "recurring": True,
            "recurring_interval": "daily"
        }
        
        mock_search_response = {
            "id": "search-456",
            "name": "Nightly Python Developer Search",
            "status": "pending",
            "search_params": search_request,
            "created_at": datetime.now().isoformat(),
            "scheduled_time": search_request["schedule_time"],
            "recurring": True,
            "recurring_interval": "daily"
        }
        
        with patch('app.services.admin_service.AdminService.create_scheduled_search', new_callable=AsyncMock) as mock_create_search:
            mock_create_search.return_value = MagicMock(**mock_search_response)
            
            search_response = client.post("/admin/scheduled-searches", json=search_request)
            assert search_response.status_code == status.HTTP_201_CREATED
            search_id = search_response.json()["id"]
        
        # 4. Monitor scheduled search
        with patch('app.services.admin_service.AdminService.get_search_by_id', new_callable=AsyncMock) as mock_get_search:
            mock_get_search.return_value = MagicMock(**mock_search_response)
            
            monitor_response = client.get(f"/admin/scheduled-searches/{search_id}")
            assert monitor_response.status_code == status.HTTP_200_OK
            monitor_data = monitor_response.json()
            assert monitor_data["status"] == "pending"
        
        # 5. Check search logs
        mock_logs = [
            {
                "id": 1,
                "search_id": search_id,
                "level": "INFO",
                "message": "Search scheduled",
                "timestamp": datetime.now().isoformat()
            }
        ]
        
        with patch('app.services.admin_service.AdminService.get_search_logs', new_callable=AsyncMock) as mock_get_logs:
            mock_get_logs.return_value = [MagicMock(**log) for log in mock_logs]
            
            logs_response = client.get(f"/admin/search-logs?search_id={search_id}")
            assert logs_response.status_code == status.HTTP_200_OK
            logs_data = logs_response.json()
            assert len(logs_data) == 1

    def test_database_job_search_workflow(self, client, db_with_sample_data):
        """Test complete workflow for database-stored job searches."""
        # 1. Search database for existing jobs
        search_response = client.get(
            "/api/v1/jobs/search_jobs?"
            "search_term=engineer&"
            "location=San Francisco&"
            "job_type=fulltime&"
            "min_salary=100000&"
            "limit=10"
        )
        
        assert search_response.status_code == status.HTTP_200_OK
        search_data = search_response.json()
        assert "jobs" in search_data
        assert "total_count" in search_data
        
        # 2. Get specific job details if jobs exist
        if search_data["jobs"]:
            job_id = search_data["jobs"][0]["id"]
            
            job_response = client.get(f"/api/v1/jobs/{job_id}")
            assert job_response.status_code == status.HTTP_200_OK
            job_data = job_response.json()
            assert job_data["id"] == job_id
            assert "job_title" in job_data
            assert "company_name" in job_data
        
        # 3. Test pagination through results
        page2_response = client.get(
            "/api/v1/jobs/search_jobs?"
            "search_term=engineer&"
            "limit=5&"
            "offset=5"
        )
        
        assert page2_response.status_code == status.HTTP_200_OK

    def test_error_handling_workflow(self, client):
        """Test complete error handling across the API."""
        # 1. Test invalid search request
        invalid_search = client.post(
            "/api/v1/search_jobs",
            json={
                "site_name": ["invalid_site"],
                "search_term": "",  # Empty search term
                "results_wanted": -10  # Invalid negative value
            }
        )
        
        assert invalid_search.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        error_data = invalid_search.json()
        assert "error" in error_data or "detail" in error_data
        
        # 2. Test service unavailable scenario
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.side_effect = Exception("Service temporarily unavailable")
            
            service_error = client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": ["indeed"],
                    "search_term": "test"
                }
            )
            
            assert service_error.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            error_data = service_error.json()
            assert "error" in error_data
        
        # 3. Test not found scenarios
        not_found = client.get("/api/v1/jobs/99999")
        assert not_found.status_code == status.HTTP_404_NOT_FOUND
        
        # 4. Test malformed JSON
        malformed_json = client.post(
            "/api/v1/search_jobs",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert malformed_json.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_authentication_workflow(self, authenticated_client, user_headers, invalid_headers):
        """Test complete authentication workflow."""
        # 1. Test unauthenticated request fails
        unauth_response = authenticated_client.post(
            "/api/v1/search_jobs",
            json={"site_name": ["indeed"], "search_term": "test"}
        )
        
        assert unauth_response.status_code == status.HTTP_403_FORBIDDEN
        
        # 2. Test invalid API key fails
        invalid_response = authenticated_client.post(
            "/api/v1/search_jobs",
            json={"site_name": ["indeed"], "search_term": "test"},
            headers=invalid_headers
        )
        
        assert invalid_response.status_code == status.HTTP_403_FORBIDDEN
        
        # 3. Test valid API key succeeds
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = ([], False)  # Empty results
            
            valid_response = authenticated_client.post(
                "/api/v1/search_jobs",
                json={"site_name": ["indeed"], "search_term": "test"},
                headers=user_headers
            )
            
            assert valid_response.status_code == status.HTTP_200_OK

    def test_caching_workflow(self, client, sample_jobs_dataframe):
        """Test complete caching workflow."""
        search_params = {
            "site_name": ["indeed"],
            "search_term": "software engineer",
            "location": "San Francisco"
        }
        
        # 1. First request - cache miss
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (sample_jobs_dataframe, False)
            
            first_response = client.post("/api/v1/search_jobs", json=search_params)
            assert first_response.status_code == status.HTTP_200_OK
            first_data = first_response.json()
            assert first_data["cached"] is False
        
        # 2. Second identical request - cache hit
        with patch('app.services.job_service.JobService.search_jobs') as mock_search_cached:
            mock_search_cached.return_value = (sample_jobs_dataframe, True)
            
            second_response = client.post("/api/v1/search_jobs", json=search_params)
            assert second_response.status_code == status.HTTP_200_OK
            second_data = second_response.json()
            assert second_data["cached"] is True
            
            # Results should be identical
            assert first_data["count"] == second_data["count"]

    def test_filtering_and_sorting_workflow(self, client, sample_jobs_dataframe):
        """Test complete filtering and sorting workflow."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search, \
             patch('app.services.job_service.JobService.filter_jobs') as mock_filter, \
             patch('app.services.job_service.JobService.sort_jobs') as mock_sort:
            
            # Mock the service calls
            mock_search.return_value = (sample_jobs_dataframe, False)
            
            # Create filtered and sorted data
            filtered_df = sample_jobs_dataframe[sample_jobs_dataframe['MIN_AMOUNT'] >= 100000]
            sorted_df = filtered_df.sort_values('MIN_AMOUNT', ascending=False)
            
            mock_filter.return_value = filtered_df
            mock_sort.return_value = sorted_df
            
            # 1. Search with filters and sorting
            response = client.get(
                "/api/v1/search_jobs?"
                "search_term=engineer&"
                "site_name=indeed&"
                "min_salary=100000&"
                "max_salary=200000&"
                "job_type=fulltime&"
                "sort_by=MIN_AMOUNT&"
                "sort_order=desc"
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # Verify filtering and sorting were applied
            mock_filter.assert_called_once()
            mock_sort.assert_called_once()
            
            # Verify response structure
            assert "jobs" in data
            assert "count" in data

    def test_csv_export_workflow(self, client, sample_jobs_dataframe):
        """Test complete CSV export workflow."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (sample_jobs_dataframe, False)
            
            # 1. Request CSV format
            response = client.get(
                "/api/v1/search_jobs?"
                "format=csv&"
                "search_term=developer&"
                "site_name=indeed"
            )
            
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "text/csv; charset=utf-8"
            
            # 2. Verify CSV content
            csv_content = response.text
            assert "TITLE,COMPANY,LOCATION" in csv_content
            assert "Software Engineer" in csv_content

    def test_hybrid_service_workflow(self, client, sample_jobs_dataframe):
        """Test hybrid service workflow with Go workers and Python fallback."""
        # This test would require the hybrid service to be properly configured
        # For now, we'll test the basic functionality
        
        with patch('app.services.hybrid_job_service.hybrid_job_service.search_jobs') as mock_hybrid:
            mock_hybrid.return_value = (sample_jobs_dataframe, False)
            
            response = client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": ["indeed"],  # Site supported by Go workers
                    "search_term": "software engineer"
                }
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["count"] > 0

    def test_performance_monitoring_workflow(self, client):
        """Test performance monitoring across multiple requests."""
        search_times = []
        
        # Make multiple requests and measure response times
        for i in range(3):
            start_time = time.time()
            
            with patch('app.services.job_service.JobService.search_jobs') as mock_search:
                mock_search.return_value = ([], False)  # Empty results for speed
                
                response = client.post(
                    "/api/v1/search_jobs",
                    json={
                        "site_name": ["indeed"],
                        "search_term": f"test_query_{i}"
                    }
                )
                
                assert response.status_code == status.HTTP_200_OK
                
            end_time = time.time()
            search_times.append(end_time - start_time)
        
        # Verify reasonable response times
        avg_time = sum(search_times) / len(search_times)
        assert avg_time < 2.0  # Should be under 2 seconds on average

    def test_concurrent_requests_workflow(self, client, sample_jobs_dataframe):
        """Test handling of concurrent requests."""
        import concurrent.futures
        
        def make_search_request(query_id):
            with patch('app.services.job_service.JobService.search_jobs') as mock_search:
                mock_search.return_value = (sample_jobs_dataframe, False)
                
                return client.post(
                    "/api/v1/search_jobs",
                    json={
                        "site_name": ["indeed"],
                        "search_term": f"test_query_{query_id}"
                    }
                )
        
        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_search_request, i) for i in range(3)]
            responses = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK

    def test_data_consistency_workflow(self, client, db_with_sample_data):
        """Test data consistency across database operations."""
        # 1. Get initial job count
        initial_response = client.get("/api/v1/jobs/search_jobs?limit=1000")
        assert initial_response.status_code == status.HTTP_200_OK
        initial_count = initial_response.json()["total_count"]
        
        # 2. Perform multiple searches - should return consistent data
        for i in range(3):
            response = client.get("/api/v1/jobs/search_jobs?limit=1000")
            assert response.status_code == status.HTTP_200_OK
            current_count = response.json()["total_count"]
            assert current_count == initial_count
        
        # 3. Test specific job retrieval consistency
        if initial_count > 0:
            jobs_response = client.get("/api/v1/jobs/search_jobs?limit=1")
            job_id = jobs_response.json()["jobs"][0]["id"]
            
            # Get same job multiple times
            for i in range(3):
                job_response = client.get(f"/api/v1/jobs/{job_id}")
                assert job_response.status_code == status.HTTP_200_OK
                job_data = job_response.json()
                assert job_data["id"] == job_id

    def test_full_api_discovery_workflow(self, client):
        """Test API discovery and documentation workflow."""
        # 1. Check root endpoint
        root_response = client.get("/")
        assert root_response.status_code == status.HTTP_200_OK
        root_data = root_response.json()
        assert "docs_url" in root_data
        
        # 2. Check OpenAPI documentation
        docs_response = client.get("/docs")
        assert docs_response.status_code == status.HTTP_200_OK
        
        # 3. Check OpenAPI JSON schema
        openapi_response = client.get("/openapi.json")
        assert openapi_response.status_code == status.HTTP_200_OK
        openapi_data = openapi_response.json()
        assert "paths" in openapi_data
        assert "info" in openapi_data