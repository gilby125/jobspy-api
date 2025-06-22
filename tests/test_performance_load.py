"""Performance and load tests for JobSpy API."""
import pytest
import time
import asyncio
import concurrent.futures
import statistics
from unittest.mock import patch, MagicMock
from fastapi import status


class TestPerformanceLoad:
    """Performance and load test cases for the JobSpy API."""

    @pytest.fixture
    def large_dataset(self):
        """Create a large dataset for performance testing."""
        import pandas as pd
        return pd.DataFrame({
            'TITLE': [f'Job Title {i}' for i in range(1000)],
            'COMPANY': [f'Company {i % 100}' for i in range(1000)],
            'LOCATION': [f'City {i % 50}' for i in range(1000)],
            'JOB_TYPE': ['fulltime'] * 1000,
            'MIN_AMOUNT': [50000 + (i * 100) for i in range(1000)],
            'MAX_AMOUNT': [80000 + (i * 100) for i in range(1000)],
            'DESCRIPTION': [f'Description for job {i}' for i in range(1000)],
            'JOB_URL': [f'http://example.com/job{i}' for i in range(1000)]
        })

    def test_single_request_response_time(self, client, sample_jobs_dataframe):
        """Test response time for a single search request."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (sample_jobs_dataframe, False)
            
            start_time = time.time()
            
            response = client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": ["indeed"],
                    "search_term": "software engineer",
                    "location": "San Francisco"
                }
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            assert response.status_code == status.HTTP_200_OK
            assert response_time < 2.0  # Should respond within 2 seconds

    def test_large_dataset_processing_time(self, client, large_dataset):
        """Test processing time with large datasets."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (large_dataset, False)
            
            start_time = time.time()
            
            response = client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": ["indeed"],
                    "search_term": "engineer",
                    "results_wanted": 1000
                }
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["count"] == 1000
            assert response_time < 5.0  # Should handle large datasets within 5 seconds

    def test_concurrent_requests_performance(self, client, sample_jobs_dataframe):
        """Test performance under concurrent load."""
        def make_request():
            with patch('app.services.job_service.JobService.search_jobs') as mock_search:
                mock_search.return_value = (sample_jobs_dataframe, False)
                
                start_time = time.time()
                response = client.post(
                    "/api/v1/search_jobs",
                    json={
                        "site_name": ["indeed"],
                        "search_term": "test",
                        "results_wanted": 20
                    }
                )
                end_time = time.time()
                
                return {
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "success": response.status_code == status.HTTP_200_OK
                }
        
        # Run 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Analyze results
        response_times = [r["response_time"] for r in results]
        success_count = sum(1 for r in results if r["success"])
        
        assert success_count == 10  # All requests should succeed
        assert statistics.mean(response_times) < 3.0  # Average response time under 3 seconds
        assert max(response_times) < 10.0  # No request should take more than 10 seconds

    def test_burst_load_handling(self, client, sample_jobs_dataframe):
        """Test handling of burst load (many requests in short time)."""
        def make_burst_request(request_id):
            with patch('app.services.job_service.JobService.search_jobs') as mock_search:
                mock_search.return_value = (sample_jobs_dataframe, False)
                
                return client.post(
                    "/api/v1/search_jobs",
                    json={
                        "site_name": ["indeed"],
                        "search_term": f"burst_test_{request_id}",
                        "results_wanted": 10
                    }
                )
        
        start_time = time.time()
        
        # Make 20 requests as quickly as possible
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_burst_request, i) for i in range(20)]
            responses = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # All requests should complete successfully
        success_count = sum(1 for r in responses if r.status_code == status.HTTP_200_OK)
        assert success_count >= 18  # Allow for some failures under extreme load
        assert total_time < 30.0  # All requests should complete within 30 seconds

    def test_memory_usage_large_requests(self, client, large_dataset):
        """Test memory usage with large response payloads."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (large_dataset, False)
            
            # Make request for large dataset
            response = client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": ["indeed"],
                    "search_term": "test",
                    "results_wanted": 1000
                }
            )
            
            assert response.status_code == status.HTTP_200_OK
            
            # Check memory usage after request
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory
            
            # Memory increase should be reasonable (less than 100MB for this test)
            assert memory_increase < 100

    def test_cpu_intensive_operations(self, client, large_dataset):
        """Test CPU usage during intensive operations like filtering/sorting."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search, \
             patch('app.services.job_service.JobService.filter_jobs') as mock_filter, \
             patch('app.services.job_service.JobService.sort_jobs') as mock_sort:
            
            # Simulate CPU-intensive operations
            def cpu_intensive_filter(df, filters):
                # Simulate complex filtering
                time.sleep(0.1)  # Simulate processing time
                return df.head(100)  # Return subset
            
            def cpu_intensive_sort(df, sort_by, sort_order):
                # Simulate complex sorting
                time.sleep(0.1)  # Simulate processing time
                return df.sort_values('TITLE')
            
            mock_search.return_value = (large_dataset, False)
            mock_filter.side_effect = cpu_intensive_filter
            mock_sort.side_effect = cpu_intensive_sort
            
            start_time = time.time()
            
            response = client.get(
                "/api/v1/search_jobs?"
                "search_term=engineer&"
                "site_name=indeed&"
                "min_salary=50000&"
                "max_salary=150000&"
                "sort_by=TITLE&"
                "sort_order=asc"
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            assert response.status_code == status.HTTP_200_OK
            assert processing_time < 5.0  # Should complete within 5 seconds

    def test_database_query_performance(self, client, db_with_sample_data):
        """Test database query performance."""
        # Test simple query performance
        start_time = time.time()
        response = client.get("/api/v1/jobs/search_jobs?limit=100")
        end_time = time.time()
        
        assert response.status_code == status.HTTP_200_OK
        query_time = end_time - start_time
        assert query_time < 1.0  # Database queries should be fast
        
        # Test complex query performance
        start_time = time.time()
        response = client.get(
            "/api/v1/jobs/search_jobs?"
            "search_term=engineer&"
            "location=San Francisco&"
            "job_type=fulltime&"
            "min_salary=100000&"
            "max_salary=200000&"
            "limit=50"
        )
        end_time = time.time()
        
        assert response.status_code == status.HTTP_200_OK
        complex_query_time = end_time - start_time
        assert complex_query_time < 2.0  # Complex queries should still be reasonably fast

    def test_health_check_performance(self, client):
        """Test health check endpoint performance."""
        response_times = []
        
        # Make multiple health check requests
        for _ in range(10):
            start_time = time.time()
            response = client.get("/health")
            end_time = time.time()
            
            assert response.status_code == status.HTTP_200_OK
            response_times.append(end_time - start_time)
        
        # Health checks should be very fast
        avg_time = statistics.mean(response_times)
        max_time = max(response_times)
        
        assert avg_time < 0.1  # Average under 100ms
        assert max_time < 0.5   # Maximum under 500ms

    def test_detailed_health_check_performance(self, client):
        """Test detailed health check performance."""
        mock_health_data = {
            "status": "healthy",
            "timestamp": time.time(),
            "services": {"database": {"status": "healthy"}},
            "system": {"memory_usage_percent": 45.2}
        }
        
        with patch('app.utils.auth_health.get_detailed_health_status') as mock_health:
            mock_health.return_value = mock_health_data
            
            response_times = []
            
            for _ in range(5):
                start_time = time.time()
                response = client.get("/health/detailed")
                end_time = time.time()
                
                assert response.status_code == status.HTTP_200_OK
                response_times.append(end_time - start_time)
            
            # Detailed health checks should still be reasonably fast
            avg_time = statistics.mean(response_times)
            assert avg_time < 1.0  # Average under 1 second

    def test_cache_performance_impact(self, client, sample_jobs_dataframe):
        """Test performance impact of caching."""
        search_params = {
            "site_name": ["indeed"],
            "search_term": "cache_test",
            "location": "Test City"
        }
        
        # First request (cache miss)
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (sample_jobs_dataframe, False)
            
            start_time = time.time()
            response1 = client.post("/api/v1/search_jobs", json=search_params)
            cache_miss_time = time.time() - start_time
            
            assert response1.status_code == status.HTTP_200_OK
            data1 = response1.json()
            assert data1["cached"] is False
        
        # Second request (cache hit)
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (sample_jobs_dataframe, True)
            
            start_time = time.time()
            response2 = client.post("/api/v1/search_jobs", json=search_params)
            cache_hit_time = time.time() - start_time
            
            assert response2.status_code == status.HTTP_200_OK
            data2 = response2.json()
            assert data2["cached"] is True
        
        # Cache hit should be significantly faster
        assert cache_hit_time < cache_miss_time
        assert cache_hit_time < 0.5  # Cache hits should be very fast

    def test_json_serialization_performance(self, client, large_dataset):
        """Test JSON serialization performance with large datasets."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (large_dataset, False)
            
            start_time = time.time()
            
            response = client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": ["indeed"],
                    "search_term": "serialization_test",
                    "results_wanted": 1000
                }
            )
            
            serialization_time = time.time() - start_time
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["jobs"]) == 1000
            
            # JSON serialization should complete within reasonable time
            assert serialization_time < 3.0

    def test_csv_export_performance(self, client, large_dataset):
        """Test CSV export performance with large datasets."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (large_dataset, False)
            
            start_time = time.time()
            
            response = client.get(
                "/api/v1/search_jobs?"
                "format=csv&"
                "search_term=csv_test&"
                "site_name=indeed&"
                "results_wanted=1000"
            )
            
            csv_time = time.time() - start_time
            
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "text/csv; charset=utf-8"
            
            # CSV generation should complete within reasonable time
            assert csv_time < 2.0

    def test_admin_dashboard_performance(self, client):
        """Test admin dashboard performance."""
        mock_stats = {
            "total_searches": 10000,
            "searches_today": 500,
            "total_jobs_found": 250000,
            "jobs_found_today": 12500,
            "active_searches": 25,
            "failed_searches_today": 12,
            "cache_hit_rate": 0.85,
            "system_health": {"api": "healthy", "database": "healthy"}
        }
        
        with patch('app.services.admin_service.AdminService.get_admin_stats') as mock_get_stats:
            mock_get_stats.return_value = MagicMock(**mock_stats)
            
            response_times = []
            
            for _ in range(5):
                start_time = time.time()
                response = client.get("/admin/dashboard")
                end_time = time.time()
                
                assert response.status_code == status.HTTP_200_OK
                response_times.append(end_time - start_time)
            
            avg_time = statistics.mean(response_times)
            assert avg_time < 1.0  # Admin dashboard should load quickly

    def test_stress_test_sustained_load(self, client, sample_jobs_dataframe):
        """Test sustained load over time."""
        def make_sustained_request():
            with patch('app.services.job_service.JobService.search_jobs') as mock_search:
                mock_search.return_value = (sample_jobs_dataframe, False)
                
                return client.post(
                    "/api/v1/search_jobs",
                    json={
                        "site_name": ["indeed"],
                        "search_term": "stress_test",
                        "results_wanted": 20
                    }
                )
        
        # Run sustained load for 30 seconds with 5 concurrent workers
        start_time = time.time()
        end_time = start_time + 30  # 30 seconds
        
        successful_requests = 0
        failed_requests = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            
            while time.time() < end_time:
                if len(futures) < 50:  # Limit pending futures
                    future = executor.submit(make_sustained_request)
                    futures.append(future)
                
                # Process completed futures
                completed_futures = []
                for future in futures:
                    if future.done():
                        try:
                            response = future.result()
                            if response.status_code == status.HTTP_200_OK:
                                successful_requests += 1
                            else:
                                failed_requests += 1
                        except Exception:
                            failed_requests += 1
                        completed_futures.append(future)
                
                # Remove completed futures
                for future in completed_futures:
                    futures.remove(future)
                
                time.sleep(0.1)  # Small delay
            
            # Wait for remaining futures
            for future in futures:
                try:
                    response = future.result(timeout=5)
                    if response.status_code == status.HTTP_200_OK:
                        successful_requests += 1
                    else:
                        failed_requests += 1
                except Exception:
                    failed_requests += 1
        
        total_requests = successful_requests + failed_requests
        success_rate = successful_requests / total_requests if total_requests > 0 else 0
        
        # Should handle sustained load with high success rate
        assert total_requests > 50  # Should process a reasonable number of requests
        assert success_rate > 0.9   # Should maintain >90% success rate

    @pytest.mark.slow
    def test_memory_leak_detection(self, client, sample_jobs_dataframe):
        """Test for memory leaks during repeated operations."""
        import psutil
        import gc
        import os
        
        process = psutil.Process(os.getpid())
        
        # Record initial memory
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform many operations
        for i in range(100):
            with patch('app.services.job_service.JobService.search_jobs') as mock_search:
                mock_search.return_value = (sample_jobs_dataframe, False)
                
                response = client.post(
                    "/api/v1/search_jobs",
                    json={
                        "site_name": ["indeed"],
                        "search_term": f"memory_test_{i}",
                        "results_wanted": 20
                    }
                )
                
                assert response.status_code == status.HTTP_200_OK
            
            # Collect garbage every 10 iterations
            if i % 10 == 0:
                gc.collect()
        
        # Check final memory
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be minimal (allowing for some normal growth)
        assert memory_increase < 50  # Less than 50MB increase

    def test_response_compression_performance(self, client, large_dataset):
        """Test response compression impact on performance."""
        with patch('app.services.job_service.JobService.search_jobs') as mock_search:
            mock_search.return_value = (large_dataset, False)
            
            # Test without compression
            start_time = time.time()
            response = client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": ["indeed"],
                    "search_term": "compression_test",
                    "results_wanted": 1000
                }
            )
            no_compression_time = time.time() - start_time
            
            assert response.status_code == status.HTTP_200_OK
            
            # Test with compression (if supported)
            start_time = time.time()
            response_compressed = client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": ["indeed"],
                    "search_term": "compression_test",
                    "results_wanted": 1000
                },
                headers={"Accept-Encoding": "gzip"}
            )
            compressed_time = time.time() - start_time
            
            assert response_compressed.status_code == status.HTTP_200_OK
            
            # Both should complete within reasonable time
            assert no_compression_time < 5.0
            assert compressed_time < 5.0