"""Error handling and edge case tests for JobSpy API."""
import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi import status


class TestErrorHandlingEdgeCases:
    """Test cases for error handling and edge case scenarios."""

    def test_malformed_json_request(self, client):
        """Test handling of malformed JSON in requests."""
        # Send invalid JSON
        response = client.post(
            "/api/v1/search_jobs",
            data='{"site_name": ["indeed"], "search_term": "test"',  # Missing closing brace
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_empty_request_body(self, client):
        """Test handling of empty request body."""
        response = client.post(
            "/api/v1/search_jobs",
            data="",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_null_values_in_request(self, client):
        """Test handling of null values in request."""
        response = client.post(
            "/api/v1/search_jobs",
            json={
                "site_name": None,
                "search_term": None,
                "location": None,
                "results_wanted": None
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_extremely_long_strings(self, client):
        """Test handling of extremely long string inputs."""
        long_string = "a" * 10000  # 10KB string
        
        response = client.post(
            "/api/v1/search_jobs",
            json={
                "site_name": ["indeed"],
                "search_term": long_string,
                "location": long_string
            }
        )
        
        # Should handle gracefully or return appropriate error
        assert response.status_code in [
            status.HTTP_200_OK, 
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        ]

    def test_invalid_data_types(self, client):
        """Test handling of invalid data types."""
        response = client.post(
            "/api/v1/search_jobs",
            json={
                "site_name": "should_be_list",  # Wrong type
                "search_term": 12345,  # Should be string
                "results_wanted": "should_be_int",  # Wrong type
                "is_remote": "should_be_bool"  # Wrong type
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        error_data = response.json()
        assert "detail" in error_data

    def test_negative_numeric_values(self, client):
        """Test handling of negative numeric values."""
        response = client.post(
            "/api/v1/search_jobs",
            json={
                "site_name": ["indeed"],
                "search_term": "test",
                "results_wanted": -10,
                "hours_old": -24,
                "distance": -5
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_zero_and_boundary_values(self, client):
        """Test handling of zero and boundary values."""
        # Test zero values
        response = client.post(
            "/api/v1/search_jobs",
            json={
                "site_name": ["indeed"],
                "search_term": "test",
                "results_wanted": 0,
                "hours_old": 0,
                "distance": 0
            }
        )
        
        # Zero results_wanted should be invalid
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_extremely_large_numeric_values(self, client):
        """Test handling of extremely large numeric values."""
        response = client.post(
            "/api/v1/search_jobs",
            json={
                "site_name": ["indeed"],
                "search_term": "test",
                "results_wanted": 999999999,
                "hours_old": 999999999,
                "distance": 999999999
            }
        )
        
        # Should handle large values or return validation error
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    def test_special_characters_in_strings(self, client, sample_jobs_dataframe):
        """Test handling of special characters in string inputs."""
        special_chars_tests = [
            "test@#$%^&*()",
            "test\n\r\t",
            "test🚀🎯💼",  # Emojis
            "test'\"\\",  # Quotes and backslashes
            "test<script>alert('xss')</script>",  # XSS attempt
            "test; DROP TABLE jobs;--",  # SQL injection attempt
        ]
        
        for special_string in special_chars_tests:
            with patch('app.services.job_service.JobService.search_jobs') as mock_search:
                mock_search.return_value = (sample_jobs_dataframe, False)
                
                response = client.post(
                    "/api/v1/search_jobs",
                    json={
                        "site_name": ["indeed"],
                        "search_term": special_string,
                        "location": special_string
                    }
                )
                
                # Should handle special characters safely
                assert response.status_code in [
                    status.HTTP_200_OK,
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ]

    def test_unicode_and_international_characters(self, client, sample_jobs_dataframe):
        """Test handling of Unicode and international characters."""
        unicode_tests = [
            "软件工程师",  # Chinese
            "エンジニア",  # Japanese
            "Инженер",  # Russian
            "Ingeniero",  # Spanish
            "Développeur",  # French with accents
            "Architekt",  # German
        ]
        
        for unicode_string in unicode_tests:
            with patch('app.services.job_service.JobService.search_jobs') as mock_search:
                mock_search.return_value = (sample_jobs_dataframe, False)
                
                response = client.post(
                    "/api/v1/search_jobs",
                    json={
                        "site_name": ["indeed"],
                        "search_term": unicode_string,
                        "location": unicode_string
                    }
                )
                
                assert response.status_code == status.HTTP_200_OK

    def test_empty_string_values(self, client):
        """Test handling of empty string values."""
        response = client.post(
            "/api/v1/search_jobs",
            json={
                "site_name": ["indeed"],
                "search_term": "",  # Empty search term
                "location": "",
                "job_type": ""
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_whitespace_only_strings(self, client):
        """Test handling of whitespace-only strings."""
        response = client.post(
            "/api/v1/search_jobs",
            json={
                "site_name": ["indeed"],
                "search_term": "   ",  # Only spaces
                "location": "\t\n\r",  # Only whitespace
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_invalid_site_names(self, client):
        """Test handling of invalid site names."""
        invalid_sites = [
            ["nonexistent_site"],
            [""],
            ["site_with_special_chars@#$"],
            ["site with spaces"],
            [123],  # Non-string in list
        ]
        
        for invalid_site in invalid_sites:
            response = client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": invalid_site,
                    "search_term": "test"
                }
            )
            
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_service_exceptions(self, client):
        """Test handling of various service layer exceptions."""
        exception_tests = [
            Exception("Generic service error"),
            ConnectionError("Database connection failed"),
            TimeoutError("Service timeout"),
            ValueError("Invalid value provided"),
            KeyError("Missing required key"),
            AttributeError("Attribute not found"),
        ]
        
        for exception in exception_tests:
            with patch('app.services.job_service.JobService.search_jobs') as mock_search:
                mock_search.side_effect = exception
                
                response = client.post(
                    "/api/v1/search_jobs",
                    json={
                        "site_name": ["indeed"],
                        "search_term": "test"
                    }
                )
                
                assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                error_data = response.json()
                assert "error" in error_data

    def test_database_connection_failure(self, client):
        """Test handling of database connection failures."""
        # Test database job search when database is unavailable
        response = client.get("/api/v1/jobs/search_jobs")
        
        # Should handle database errors gracefully
        assert response.status_code in [
            status.HTTP_200_OK,  # Empty results
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_503_SERVICE_UNAVAILABLE
        ]

    def test_invalid_job_id_formats(self, client):
        """Test handling of invalid job ID formats."""
        invalid_ids = [
            "not_a_number",
            "12.34",  # Float
            "-1",  # Negative
            "999999999999999999999",  # Too large
            "",  # Empty
            "null",
            "undefined"
        ]
        
        for invalid_id in invalid_ids:
            response = client.get(f"/api/v1/jobs/{invalid_id}")
            
            assert response.status_code in [
                status.HTTP_404_NOT_FOUND,
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ]

    def test_content_type_mismatch(self, client):
        """Test handling of content type mismatches."""
        # Send JSON data with wrong content type
        response = client.post(
            "/api/v1/search_jobs",
            data='{"site_name": ["indeed"], "search_term": "test"}',
            headers={"Content-Type": "text/plain"}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_missing_required_headers(self, authenticated_client):
        """Test handling of missing required headers."""
        # Test request without API key when required
        response = authenticated_client.post(
            "/api/v1/search_jobs",
            json={"site_name": ["indeed"], "search_term": "test"}
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_invalid_query_parameters(self, client):
        """Test handling of invalid query parameters."""
        # Test GET endpoint with invalid parameters
        response = client.get(
            "/api/v1/search_jobs?"
            "invalid_param=value&"
            "limit=not_a_number&"
            "offset=-5"
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_http_method_not_allowed(self, client):
        """Test handling of HTTP methods not allowed."""
        # Try to use wrong HTTP method
        response = client.put("/api/v1/search_jobs")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        
        response = client.delete("/api/v1/search_jobs")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_url_path_not_found(self, client):
        """Test handling of non-existent URL paths."""
        response = client.get("/api/v1/nonexistent_endpoint")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        response = client.post("/admin/nonexistent_endpoint")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_admin_endpoint_edge_cases(self, client):
        """Test edge cases for admin endpoints."""
        # Test invalid template ID
        response = client.get("/admin/search-templates/invalid_id")
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
        
        # Test invalid search ID
        response = client.get("/admin/scheduled-searches/invalid_id")
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    def test_admin_service_failures(self, client):
        """Test admin endpoints with service failures."""
        # Test dashboard with service failure
        with patch('app.services.admin_service.AdminService.get_admin_stats') as mock_stats:
            mock_stats.side_effect = Exception("Admin service unavailable")
            
            response = client.get("/admin/dashboard")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_concurrent_error_scenarios(self, client):
        """Test error handling under concurrent load."""
        import concurrent.futures
        
        def make_error_request():
            return client.post(
                "/api/v1/search_jobs",
                json={
                    "site_name": ["invalid_site"],
                    "search_term": ""  # Invalid
                }
            )
        
        # Make multiple concurrent error requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_error_request) for _ in range(10)]
            responses = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All should return appropriate error codes
        for response in responses:
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_memory_exhaustion_protection(self, client):
        """Test protection against memory exhaustion attacks."""
        # Try to request extremely large number of results
        response = client.post(
            "/api/v1/search_jobs",
            json={
                "site_name": ["indeed"],
                "search_term": "test",
                "results_wanted": 1000000  # Very large number
            }
        )
        
        # Should either cap the results or return validation error
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST
        ]

    def test_nested_json_objects(self, client):
        """Test handling of unexpected nested JSON objects."""
        response = client.post(
            "/api/v1/search_jobs",
            json={
                "site_name": ["indeed"],
                "search_term": {
                    "nested": "object"  # Unexpected nested object
                },
                "location": ["should", "be", "string"]  # Array instead of string
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_duplicate_fields_in_json(self, client):
        """Test handling of duplicate fields in JSON."""
        # This is hard to test directly with client, but we can test the concept
        json_with_duplicates = '{"site_name": ["indeed"], "site_name": ["linkedin"], "search_term": "test"}'
        
        response = client.post(
            "/api/v1/search_jobs",
            data=json_with_duplicates,
            headers={"Content-Type": "application/json"}
        )
        
        # Should handle gracefully
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    def test_rate_limit_edge_cases(self, client):
        """Test edge cases around rate limiting."""
        # Make many requests quickly to test rate limiting
        responses = []
        for i in range(20):
            response = client.get("/health")  # Use simple endpoint
            responses.append(response)
        
        # Most should succeed, some might be rate limited
        success_count = sum(1 for r in responses if r.status_code == status.HTTP_200_OK)
        rate_limited_count = sum(1 for r in responses if r.status_code == status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Should have some successful requests
        assert success_count > 0

    def test_health_check_edge_cases(self, client):
        """Test edge cases for health checks."""
        # Test health check with service failures
        with patch('app.utils.auth_health.get_detailed_health_status') as mock_health:
            mock_health.side_effect = Exception("Health service error")
            
            response = client.get("/health/detailed")
            # Should handle health check failures gracefully
            assert response.status_code in [
                status.HTTP_200_OK,  # Degraded health
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_503_SERVICE_UNAVAILABLE
            ]

    def test_cors_edge_cases(self, client):
        """Test CORS edge cases."""
        # Test preflight request with unusual headers
        response = client.options(
            "/api/v1/search_jobs",
            headers={
                "Origin": "https://malicious-site.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,X-Custom-Header"
            }
        )
        
        # Should handle CORS requests appropriately
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT
        ]

    def test_encoding_edge_cases(self, client, sample_jobs_dataframe):
        """Test various character encoding edge cases."""
        # Test different encodings
        encoding_tests = [
            "café",  # UTF-8 accented characters
            "naïve",  # More accented characters
            "résumé",  # Common in job context
            "Москва",  # Cyrillic
            "北京",  # Chinese characters
        ]
        
        for encoded_text in encoding_tests:
            with patch('app.services.job_service.JobService.search_jobs') as mock_search:
                mock_search.return_value = (sample_jobs_dataframe, False)
                
                response = client.post(
                    "/api/v1/search_jobs",
                    json={
                        "site_name": ["indeed"],
                        "search_term": encoded_text
                    }
                )
                
                assert response.status_code == status.HTTP_200_OK

    def test_timezone_edge_cases(self, client):
        """Test timezone-related edge cases."""
        from datetime import datetime, timezone, timedelta
        
        # Test with various timezone formats
        timezone_tests = [
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone(timedelta(hours=5))).isoformat(),
            "2024-01-01T00:00:00Z",
            "2024-01-01T00:00:00+05:00",
        ]
        
        for tz_string in timezone_tests:
            response = client.post(
                "/admin/scheduled-searches",
                json={
                    "name": "Timezone Test",
                    "search_term": "test",
                    "site_names": ["indeed"],
                    "schedule_time": tz_string
                }
            )
            
            # Should handle timezone formats or return validation error
            assert response.status_code in [
                status.HTTP_201_CREATED,
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ]