"""Real integration tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient

from tests.fixtures.sample_data import get_sample_search_params, get_error_scenario


class TestAPIRealIntegration:
    """Test API endpoints with real functionality."""

    def test_health_endpoint_real(self, real_client):
        """Test health endpoint with real response."""
        response = real_client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_root_endpoint_real(self, real_client):
        """Test root endpoint with real response."""
        response = real_client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "docs_url" in data

    def test_search_jobs_post_real(self, real_client):
        """Test job search POST endpoint with real JobSpy integration."""
        search_params = get_sample_search_params("basic_search")
        search_params["results_wanted"] = 3
        
        response = real_client.post("/api/v1/search_jobs", json=search_params)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "count" in data
        assert "jobs" in data
        assert "cached" in data

    def test_search_jobs_get_real(self, real_client):
        """Test job search GET endpoint with real parameters."""
        response = real_client.get(
            "/api/v1/search_jobs",
            params={
                "site_name": "indeed",
                "search_term": "python",
                "results_wanted": 2
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "jobs" in data

    def test_csv_export_real(self, real_client):
        """Test CSV export with real data."""
        response = real_client.get(
            "/api/v1/search_jobs",
            params={
                "site_name": "indeed",
                "search_term": "developer",
                "results_wanted": 2,
                "format": "csv"
            }
        )
        
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]

    def test_validation_errors_real(self, real_client):
        """Test validation with real error scenarios."""
        invalid_params = get_error_scenario("negative_results")
        
        response = real_client.post("/api/v1/search_jobs", json=invalid_params)
        
        assert response.status_code == 422
        data = response.json()
        assert "error" in data or "detail" in data

    def test_caching_behavior_real(self, real_client):
        """Test caching behavior with real requests."""
        search_params = {
            "site_name": ["indeed"],
            "search_term": "test_cache",
            "results_wanted": 1
        }
        
        # First request
        response1 = real_client.post("/api/v1/search_jobs", json=search_params)
        assert response1.status_code == 200
        
        # Second request
        response2 = real_client.post("/api/v1/search_jobs", json=search_params)
        assert response2.status_code == 200

    def test_openapi_docs_real(self, real_client):
        """Test API documentation endpoints."""
        # Test OpenAPI JSON
        response = real_client.get("/openapi.json")
        assert response.status_code == 200
        
        data = response.json()
        assert "openapi" in data
        assert "paths" in data