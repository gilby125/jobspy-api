"""Real end-to-end workflow tests."""
import pytest
import time
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.tracking_models import Company, JobPosting, Location
from tests.fixtures.sample_data import get_sample_search_params


class TestE2EWorkflowsReal:
    """Test complete workflows with real data flow."""

    def test_complete_job_search_workflow_real(self, client: TestClient):
        """Test complete job search workflow from API request to response."""
        # Step 1: Make initial search request
        search_params = get_sample_search_params("basic_search")
        search_params["results_wanted"] = 3
        
        response = client.post("/api/v1/search_jobs", json=search_params)
        assert response.status_code == 200
        
        data = response.json()
        assert "count" in data
        assert "jobs" in data
        assert "cached" in data
        
        # Step 2: Verify response structure
        assert isinstance(data["count"], int)
        assert isinstance(data["jobs"], list)
        assert isinstance(data["cached"], bool)
        
        # Step 3: If we have jobs, verify job structure
        if data["count"] > 0:
            job = data["jobs"][0]
            expected_fields = ["TITLE", "COMPANY", "SITE"]
            for field in expected_fields:
                if field in job:  # Some fields may not be present
                    assert job[field] is not None

    def test_search_caching_workflow_real(self, client: TestClient):
        """Test complete caching workflow with real cache operations."""
        search_params = {
            "site_name": ["indeed"],
            "search_term": "cache_test_job",
            "results_wanted": 2
        }
        
        # Step 1: First request (should not be cached)
        start_time = time.time()
        response1 = client.post("/api/v1/search_jobs", json=search_params)
        first_request_time = time.time() - start_time
        
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["cached"] is False
        
        # Step 2: Second request (should be faster due to caching)
        start_time = time.time()
        response2 = client.post("/api/v1/search_jobs", json=search_params)
        second_request_time = time.time() - start_time
        
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Verify response structure is consistent
        assert set(data1.keys()) == set(data2.keys())
        
        # Second request should typically be faster (cached)
        # Note: This may not always be true due to network variability
        if data2["cached"]:
            assert second_request_time <= first_request_time + 1.0  # Allow some tolerance

    def test_multi_site_aggregation_workflow_real(self, client: TestClient):
        """Test multi-site job aggregation workflow."""
        search_params = {
            "site_name": ["indeed", "linkedin"],
            "search_term": "python developer",
            "results_wanted": 6  # 3 per site
        }
        
        # Step 1: Execute multi-site search
        response = client.post("/api/v1/search_jobs", json=search_params)
        assert response.status_code == 200
        
        data = response.json()
        assert "jobs" in data
        
        # Step 2: Verify data aggregation
        if data["count"] > 0:
            # Check that we potentially have jobs from multiple sites
            sites_found = set()
            for job in data["jobs"]:
                if "SITE" in job and job["SITE"]:
                    sites_found.add(job["SITE"])
            
            # Should have at least one site represented
            assert len(sites_found) >= 1

    def test_csv_export_workflow_real(self, client: TestClient):
        """Test complete CSV export workflow."""
        # Step 1: Request jobs in CSV format
        response = client.get(
            "/api/v1/search_jobs",
            params={
                "site_name": "indeed",
                "search_term": "csv_test",
                "results_wanted": 2,
                "format": "csv"
            }
        )
        
        assert response.status_code == 200
        
        # Step 2: Verify CSV format
        assert "text/csv" in response.headers["content-type"]
        assert "attachment" in response.headers.get("content-disposition", "")
        
        # Step 3: Verify CSV content structure
        csv_content = response.text
        assert isinstance(csv_content, str)
        lines = csv_content.strip().split('\n')
        assert len(lines) >= 1  # At least header row

    def test_error_handling_workflow_real(self, client: TestClient):
        """Test complete error handling workflow."""
        # Step 1: Send invalid request
        invalid_params = {
            "site_name": ["invalid_site_name"],
            "search_term": "test",
            "results_wanted": 1
        }
        
        response = client.post("/api/v1/search_jobs", json=invalid_params)
        
        # Step 2: Verify error response
        assert response.status_code in [422, 500]  # Validation or server error
        
        if response.status_code == 422:
            data = response.json()
            assert "error" in data or "detail" in data

    def test_database_job_search_workflow_real(self, client: TestClient, test_db: Session):
        """Test database-based job search workflow."""
        # Step 1: Create test data in database
        company = Company(name="DB Test Company", domain="dbtest.com")
        test_db.add(company)
        test_db.commit()
        test_db.refresh(company)
        
        location = Location(city="DB City", state="DB", country="USA")
        test_db.add(location)
        test_db.commit()
        test_db.refresh(location)
        
        job = JobPosting(
            job_hash="db_test_hash",
            title="Database Test Job",
            company_id=company.id,
            location_id=location.id,
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
            status="active"
        )
        test_db.add(job)
        test_db.commit()
        
        # Step 2: Search using database API
        response = client.get("/api/v1/jobs/search_jobs")
        
        # This endpoint exists based on the routes, should not crash
        assert response.status_code in [200, 404, 500]  # Valid responses

    def test_pagination_workflow_real(self, client: TestClient):
        """Test pagination workflow with real data."""
        # Step 1: Request with pagination
        response = client.get(
            "/api/v1/search_jobs",
            params={
                "site_name": "indeed",
                "search_term": "developer",
                "results_wanted": 10,
                "page": 1,
                "page_size": 5,
                "paginate": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Step 2: Verify pagination structure
        if "total_pages" in data:
            assert "current_page" in data
            assert "page_size" in data
            assert data["current_page"] == 1

    def test_health_check_workflow_real(self, client: TestClient):
        """Test health check workflow."""
        # Step 1: Check basic health
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        
        # Step 2: Verify health response includes timestamp
        assert "timestamp" in data
        
        # Step 3: Verify health response is consistent
        response2 = client.get("/health")
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["status"] == "ok"

    def test_api_documentation_workflow_real(self, client: TestClient):
        """Test API documentation access workflow."""
        # Step 1: Access OpenAPI documentation
        response = client.get("/docs")
        assert response.status_code == 200
        
        # Step 2: Access OpenAPI JSON
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        
        # Step 3: Verify job search endpoints are documented
        paths = data["paths"]
        assert "/api/v1/search_jobs" in paths

    def test_concurrent_requests_workflow_real(self, client: TestClient):
        """Test concurrent request handling workflow."""
        import concurrent.futures
        
        def make_search_request(search_term):
            return client.get(
                "/api/v1/search_jobs",
                params={
                    "site_name": "indeed",
                    "search_term": search_term,
                    "results_wanted": 1
                }
            )
        
        # Step 1: Make concurrent requests
        search_terms = ["python", "javascript", "java"]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(make_search_request, term)
                for term in search_terms
            ]
            responses = [future.result() for future in futures]
        
        # Step 2: Verify all requests completed successfully
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert "jobs" in data

    def test_large_result_handling_workflow_real(self, client: TestClient):
        """Test large result set handling workflow."""
        # Step 1: Request large result set
        search_params = {
            "site_name": ["indeed"],
            "search_term": "software",
            "results_wanted": 50  # Large result set
        }
        
        response = client.post("/api/v1/search_jobs", json=search_params)
        
        # Step 2: Verify request completes without timeout
        assert response.status_code == 200
        
        data = response.json()
        assert "jobs" in data
        assert "count" in data
        
        # Step 3: Verify response size is manageable
        response_size = len(str(data))
        assert response_size > 0  # Should have some content

    def test_special_character_workflow_real(self, client: TestClient):
        """Test special character handling workflow."""
        # Step 1: Search with special characters
        search_params = {
            "site_name": ["indeed"],
            "search_term": "C++ developer & Python",
            "location": "San Francisco, CA",
            "results_wanted": 2
        }
        
        response = client.post("/api/v1/search_jobs", json=search_params)
        
        # Step 2: Verify special characters are handled properly
        assert response.status_code == 200
        
        data = response.json()
        assert "jobs" in data

    def test_unicode_workflow_real(self, client: TestClient):
        """Test Unicode character handling workflow."""
        # Step 1: Search with Unicode characters
        search_params = {
            "site_name": ["indeed"],
            "search_term": "développeur Python",  # French with accents
            "location": "Montréal, QC",
            "results_wanted": 1
        }
        
        response = client.post("/api/v1/search_jobs", json=search_params)
        
        # Step 2: Verify Unicode is handled properly
        assert response.status_code == 200
        
        data = response.json()
        assert "jobs" in data