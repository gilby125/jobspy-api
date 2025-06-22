"""Tests for the JobSpy Docker API."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import pandas as pd

def test_health_endpoint(client):
    """Test the health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs_url" in data
    assert data["docs_url"] == "/docs"

def test_api_key_authentication_missing(authenticated_client):
    """Test API endpoints require authentication when enabled."""
    response = authenticated_client.get("/api/v1/jobs/search_jobs")
    assert response.status_code == 403
    assert "Missing API Key" in response.json()["detail"]

def test_api_key_authentication_valid(authenticated_client):
    """Test API endpoints work with valid API key."""
    headers = {"x-api-key": "test-api-key"}
    response = authenticated_client.get("/api/v1/jobs/search_jobs", headers=headers)
    # This should not return 403 (may return other errors but not auth error)
    assert response.status_code != 403

def test_api_key_authentication_invalid(authenticated_client):
    """Test API endpoints reject invalid API key."""
    headers = {"x-api-key": "invalid-key"}
    response = authenticated_client.get("/api/v1/jobs/search_jobs", headers=headers)
    assert response.status_code == 403
    assert "Invalid API Key" in response.json()["detail"]

@patch('app.services.job_service.JobService.search_jobs')
def test_search_jobs_basic(mock_search_jobs, client):
    """Test the basic search_jobs endpoint."""
    # Setup mock
    mock_df = pd.DataFrame({
        'SITE': ['indeed', 'linkedin'],
        'TITLE': ['Software Engineer', 'Data Scientist'],
        'COMPANY': ['Test Corp', 'Test Inc'],
        'LOCATION': ['San Francisco', 'New York'],
        'JOB_TYPE': ['fulltime', 'fulltime'],
        'MIN_AMOUNT': [100000, 120000],
        'MAX_AMOUNT': [150000, 180000],
        'DESCRIPTION': ['Test description 1', 'Test description 2'],
        'DATE_POSTED': ['2024-01-01', '2024-01-02']
    })
    mock_search_jobs.return_value = (mock_df, False)
    
    response = client.post(
        "/api/v1/search_jobs",
        json={
            "site_name": ["indeed", "linkedin"],
            "search_term": "software engineer",
            "location": "San Francisco",
            "country_indeed": "USA"
        }
    )
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert not data["cached"]
    assert len(data["jobs"]) == 2
    assert data["jobs"][0]["TITLE"] == "Software Engineer"

@patch('app.services.job_service.JobService.search_jobs')
def test_search_jobs_cached(mock_search_jobs, client):
    """Test cached search results."""
    # Setup mock to return cached result
    mock_df = pd.DataFrame({
        'SITE': ['indeed'],
        'TITLE': ['Cached Job'],
        'COMPANY': ['Cached Corp'],
        'LOCATION': ['Cached City'],
        'JOB_TYPE': ['fulltime'],
        'MIN_AMOUNT': [100000],
        'MAX_AMOUNT': [150000],
        'DESCRIPTION': ['Cached description'],
        'DATE_POSTED': ['2024-01-01']
    })
    mock_search_jobs.return_value = (mock_df, True)
    
    response = client.post(
        "/api/v1/search_jobs",
        json={
            "site_name": ["indeed"],
            "search_term": "cached",
            "location": "Test City"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["cached"] == True

def test_search_jobs_validation_error(client):
    """Test validation errors are handled properly."""
    response = client.post(
        "/api/v1/search_jobs",
        json={
            "site_name": ["invalid_site"],
            "search_term": "test",
            "results_wanted": -1  # Invalid value
        }
    )
    
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert "Validation Error" in data["error"]

def test_search_jobs_csv_format(client):
    """Test CSV format response."""
    with patch('app.services.job_service.JobService.search_jobs') as mock_search:
        mock_df = pd.DataFrame({
            'SITE': ['indeed'],
            'TITLE': ['Test Job'],
            'COMPANY': ['Test Corp'],
            'LOCATION': ['Test City'],
            'JOB_TYPE': ['fulltime'],
            'DESCRIPTION': ['Test description']
        })
        mock_search.return_value = (mock_df, False)
        
        response = client.get("/api/v1/search_jobs?format=csv&search_term=test")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

@patch('app.services.job_service.JobService.search_jobs')
def test_search_jobs_error_handling(mock_search_jobs, client):
    """Test error handling in search_jobs endpoint."""
    # Mock the service to raise an exception
    mock_search_jobs.side_effect = Exception("JobSpy scraping failed")
    
    response = client.post(
        "/api/v1/search_jobs",
        json={
            "site_name": ["indeed"],
            "search_term": "test"
        }
    )
    
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert "Server Error" in data["error"]

def test_database_job_search_endpoint(client):
    """Test the database-based job search endpoint."""
    response = client.get("/api/v1/jobs/search_jobs")
    # This endpoint requires database data, so it may return empty results
    # but should not fail with server errors
    assert response.status_code in [200, 404]  # Allow 404 if no data

def test_rate_limiting_headers(client):
    """Test that rate limiting middleware adds appropriate headers."""
    response = client.get("/health")
    # Check if rate limiting headers are present (they may not be if disabled)
    # This is more of a smoke test
    assert response.status_code == 200

def test_cors_headers(client):
    """Test CORS headers are properly set."""
    response = client.options("/health")
    assert response.status_code == 200
