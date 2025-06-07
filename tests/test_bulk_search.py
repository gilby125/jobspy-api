import pytest
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.models.admin_models import BulkSearchRequest, ScheduledSearchRequest

client = TestClient(app)

def test_bulk_search_endpoint():
    """Test the bulk search API endpoint"""
    
    # Create test bulk search request
    bulk_request = {
        "batch_name": "Test Batch",
        "searches": [
            {
                "name": "Python Jobs SF",
                "search_term": "python developer",
                "location": "San Francisco, CA",
                "site_names": ["indeed"],
                "results_wanted": 10,
                "recurring": False
            },
            {
                "name": "Remote JS Jobs",
                "search_term": "javascript developer remote",
                "location": "",
                "site_names": ["linkedin", "indeed"],
                "results_wanted": 20,
                "recurring": True,
                "recurring_interval": "daily"
            }
        ]
    }
    
    # Send POST request to bulk search endpoint
    response = client.post(
        "/admin/searches/bulk",
        json=bulk_request,
        headers={"Content-Type": "application/json"}
    )
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "batch_name" in data
    assert "total_searches" in data
    assert "successful" in data
    assert "failed" in data
    assert "searches" in data
    
    # Verify batch details
    assert data["batch_name"] == "Test Batch"
    assert data["total_searches"] == 2
    assert data["successful"] >= 0
    assert data["failed"] >= 0
    assert len(data["searches"]) == 2
    
    # Verify individual search responses
    for search in data["searches"]:
        assert "id" in search
        assert "name" in search
        assert "status" in search
        assert "batch_name" in search
        assert search["batch_name"] == "Test Batch"


def test_bulk_search_with_recurring():
    """Test bulk search with recurring searches"""
    
    future_time = (datetime.now() + timedelta(hours=1)).isoformat()
    
    bulk_request = {
        "batch_name": "Recurring Test Batch",
        "searches": [
            {
                "name": "Daily Python Jobs",
                "search_term": "python developer",
                "location": "New York, NY",
                "site_names": ["indeed"],
                "results_wanted": 15,
                "recurring": True,
                "recurring_interval": "daily",
                "schedule_time": future_time
            }
        ]
    }
    
    response = client.post(
        "/admin/searches/bulk",
        json=bulk_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify recurring search was scheduled
    assert data["total_searches"] == 1
    search = data["searches"][0]
    assert search["recurring"] == True
    assert search["recurring_interval"] == "daily"


def test_bulk_search_empty_request():
    """Test bulk search with empty searches list"""
    
    bulk_request = {
        "batch_name": "Empty Batch",
        "searches": []
    }
    
    response = client.post(
        "/admin/searches/bulk",
        json=bulk_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["total_searches"] == 0
    assert data["successful"] == 0
    assert data["failed"] == 0
    assert len(data["searches"]) == 0


def test_bulk_search_invalid_data():
    """Test bulk search with invalid search data"""
    
    bulk_request = {
        "batch_name": "Invalid Data Batch",
        "searches": [
            {
                "name": "",  # Empty name should cause validation issues
                "search_term": "",  # Empty search term
                "site_names": [],
                "results_wanted": -5  # Invalid number
            }
        ]
    }
    
    response = client.post(
        "/admin/searches/bulk",
        json=bulk_request,
        headers={"Content-Type": "application/json"}
    )
    
    # Should still return 200 but with failed searches
    assert response.status_code == 200 or response.status_code == 422  # Validation error is also acceptable


def test_bulk_search_admin_page_contains_section():
    """Test that the admin searches page contains the bulk search section"""
    
    response = client.get("/admin/searches")
    assert response.status_code == 200
    
    html_content = response.text
    assert "Bulk Search Operations" in html_content
    assert "addBulkSearch()" in html_content
    assert "submitBulkSearches()" in html_content
    assert "bulk-batch-name" in html_content


if __name__ == "__main__":
    pytest.main([__file__])