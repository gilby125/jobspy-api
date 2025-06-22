"""Real performance tests for the JobSpy API."""
import pytest
import time
import asyncio
import concurrent.futures
from fastapi.testclient import TestClient
from typing import List, Dict, Any

from tests.fixtures.sample_data import get_sample_search_params


class TestPerformanceReal:
    """Test API performance with real requests."""

    def test_health_endpoint_performance_real(self, performance_client: TestClient):
        """Test health endpoint response time."""
        start_time = time.time()
        response = performance_client.get("/health")
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        assert response_time < 1.0  # Should respond within 1 second

    def test_basic_search_performance_real(self, performance_client: TestClient):
        """Test basic job search performance."""
        search_params = {
            "site_name": ["indeed"],
            "search_term": "python",
            "results_wanted": 5
        }
        
        start_time = time.time()
        response = performance_client.post("/api/v1/search_jobs", json=search_params)
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        assert response_time < 30.0  # Should complete within 30 seconds
        
        data = response.json()
        assert "jobs" in data

    def test_cached_request_performance_real(self, performance_client: TestClient):
        """Test cached request performance improvement."""
        search_params = {
            "site_name": ["indeed"],
            "search_term": "performance_test",
            "results_wanted": 3
        }
        
        # First request (not cached)
        start_time = time.time()
        response1 = performance_client.post("/api/v1/search_jobs", json=search_params)
        first_request_time = time.time() - start_time
        
        assert response1.status_code == 200
        
        # Second request (potentially cached)
        start_time = time.time()
        response2 = performance_client.post("/api/v1/search_jobs", json=search_params)
        second_request_time = time.time() - start_time
        
        assert response2.status_code == 200
        
        # If cached, second request should be significantly faster
        data2 = response2.json()
        if data2.get("cached", False):
            assert second_request_time < first_request_time

    def test_concurrent_requests_performance_real(self, performance_client: TestClient):
        """Test performance under concurrent load."""
        def make_request(request_id: int) -> Dict[str, Any]:
            search_params = {
                "site_name": ["indeed"],
                "search_term": f"concurrent_test_{request_id}",
                "results_wanted": 2
            }
            
            start_time = time.time()
            response = performance_client.post("/api/v1/search_jobs", json=search_params)
            response_time = time.time() - start_time
            
            return {
                "request_id": request_id,
                "status_code": response.status_code,
                "response_time": response_time,
                "success": response.status_code == 200
            }
        
        # Run 5 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request, i) for i in range(5)]
            results = [future.result() for future in futures]
        
        # Verify all requests completed successfully
        for result in results:
            assert result["success"] is True
            assert result["response_time"] < 60.0  # Each request within 60 seconds
        
        # Calculate average response time
        avg_response_time = sum(r["response_time"] for r in results) / len(results)
        assert avg_response_time < 45.0  # Average should be reasonable

    def test_multiple_site_search_performance_real(self, performance_client: TestClient):
        """Test performance of multi-site searches."""
        search_params = {
            "site_name": ["indeed", "linkedin"],
            "search_term": "software engineer",
            "results_wanted": 8  # 4 per site
        }
        
        start_time = time.time()
        response = performance_client.post("/api/v1/search_jobs", json=search_params)
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        assert response_time < 60.0  # Multi-site search within 60 seconds
        
        data = response.json()
        assert "jobs" in data

    def test_large_result_set_performance_real(self, performance_client: TestClient):
        """Test performance with larger result sets."""
        search_params = {
            "site_name": ["indeed"],
            "search_term": "developer",
            "results_wanted": 25  # Larger result set
        }
        
        start_time = time.time()
        response = performance_client.post("/api/v1/search_jobs", json=search_params)
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        assert response_time < 45.0  # Large result set within 45 seconds

    def test_csv_export_performance_real(self, performance_client: TestClient):
        """Test CSV export performance."""
        start_time = time.time()
        response = performance_client.get(
            "/api/v1/search_jobs",
            params={
                "site_name": "indeed",
                "search_term": "csv_performance",
                "results_wanted": 5,
                "format": "csv"
            }
        )
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        assert response_time < 30.0  # CSV export within 30 seconds
        assert "text/csv" in response.headers["content-type"]

    def test_api_documentation_performance_real(self, performance_client: TestClient):
        """Test API documentation loading performance."""
        # Test OpenAPI JSON performance
        start_time = time.time()
        response = performance_client.get("/openapi.json")
        openapi_time = time.time() - start_time
        
        assert response.status_code == 200
        assert openapi_time < 2.0  # OpenAPI JSON within 2 seconds
        
        # Test docs page performance
        start_time = time.time()
        response = performance_client.get("/docs")
        docs_time = time.time() - start_time
        
        assert response.status_code == 200
        assert docs_time < 3.0  # Docs page within 3 seconds

    def test_error_response_performance_real(self, performance_client: TestClient):
        """Test error response performance."""
        invalid_params = {
            "site_name": ["invalid_site"],
            "search_term": "test"
        }
        
        start_time = time.time()
        response = performance_client.post("/api/v1/search_jobs", json=invalid_params)
        response_time = time.time() - start_time
        
        # Error responses should be fast
        assert response_time < 5.0
        assert response.status_code in [422, 500]

    def test_memory_usage_stability_real(self, performance_client: TestClient):
        """Test memory usage stability over multiple requests."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Make multiple requests
        for i in range(10):
            search_params = {
                "site_name": ["indeed"],
                "search_term": f"memory_test_{i}",
                "results_wanted": 2
            }
            response = performance_client.post("/api/v1/search_jobs", json=search_params)
            assert response.status_code == 200
        
        # Check final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100

    def test_response_size_efficiency_real(self, performance_client: TestClient):
        """Test response size efficiency."""
        search_params = {
            "site_name": ["indeed"],
            "search_term": "response_size_test",
            "results_wanted": 5
        }
        
        response = performance_client.post("/api/v1/search_jobs", json=search_params)
        assert response.status_code == 200
        
        # Check response size
        response_size = len(response.content)
        
        # Response should be reasonable size (less than 1MB for 5 jobs)
        assert response_size < 1024 * 1024  # 1MB
        
        data = response.json()
        if data["count"] > 0:
            # Calculate approximate size per job
            size_per_job = response_size / data["count"]
            assert size_per_job < 200 * 1024  # Less than 200KB per job

    def test_database_query_performance_real(self, performance_client: TestClient):
        """Test database query performance."""
        start_time = time.time()
        response = performance_client.get("/api/v1/jobs/search_jobs")
        response_time = time.time() - start_time
        
        # Database queries should be fast
        assert response_time < 5.0
        assert response.status_code in [200, 404]  # Valid responses

    def test_repeated_identical_requests_performance_real(self, performance_client: TestClient):
        """Test performance of repeated identical requests (cache effectiveness)."""
        search_params = {
            "site_name": ["indeed"],
            "search_term": "cache_effectiveness_test",
            "results_wanted": 3
        }
        
        response_times = []
        
        # Make 5 identical requests
        for i in range(5):
            start_time = time.time()
            response = performance_client.post("/api/v1/search_jobs", json=search_params)
            response_time = time.time() - start_time
            response_times.append(response_time)
            
            assert response.status_code == 200
        
        # Later requests should generally be faster due to caching
        # (though this may not always be true due to cache TTL)
        assert all(rt < 60.0 for rt in response_times)  # All requests reasonable

    def test_load_spike_handling_real(self, performance_client: TestClient):
        """Test handling of sudden load spikes."""
        def burst_request(request_id: int) -> bool:
            try:
                response = performance_client.get("/health")
                return response.status_code == 200
            except Exception:
                return False
        
        # Simulate a burst of requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(burst_request, i) for i in range(20)]
            results = [future.result() for future in futures]
        
        # Most requests should succeed (allow some failures under load)
        success_rate = sum(results) / len(results)
        assert success_rate >= 0.8  # At least 80% success rate