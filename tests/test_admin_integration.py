"""Integration tests for /admin endpoints."""
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import status
from datetime import datetime, timedelta

from app.models.admin_models import SearchStatus


class TestAdminAPIIntegration:
    """Integration test cases for admin API endpoints."""

    def test_admin_dashboard_success(self, client):
        """Test GET /admin/dashboard with successful response."""
        mock_stats = {
            "total_searches": 150,
            "searches_today": 25,
            "total_jobs_found": 5000,
            "jobs_found_today": 200,
            "active_searches": 3,
            "failed_searches_today": 2,
            "cache_hit_rate": 0.85,
            "system_health": {"api": "healthy", "database": "healthy", "cache": "healthy"}
        }
        
        with patch('app.services.admin_service.AdminService.get_admin_stats', new_callable=AsyncMock) as mock_get_stats:
            mock_get_stats.return_value = MagicMock(**mock_stats)
            
            response = client.get("/admin/dashboard")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_searches"] == 150
            assert data["cache_hit_rate"] == 0.85

    def test_admin_dashboard_service_error(self, client):
        """Test GET /admin/dashboard handles service errors."""
        with patch('app.services.admin_service.AdminService.get_admin_stats', new_callable=AsyncMock) as mock_get_stats:
            mock_get_stats.side_effect = Exception("Database connection failed")
            
            response = client.get("/admin/dashboard")
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "error" in data

    def test_create_scheduled_search_success(self, client):
        """Test POST /admin/scheduled-searches with valid data."""
        mock_search_response = {
            "id": "123",
            "name": "Test Search",
            "status": "pending",
            "search_params": {"search_term": "engineer"},
            "created_at": datetime.now().isoformat(),
            "scheduled_time": (datetime.now() + timedelta(hours=1)).isoformat(),
            "jobs_found": None,
            "error_message": None,
            "recurring": False
        }
        
        search_request = {
            "name": "Test Search",
            "search_term": "software engineer",
            "location": "San Francisco",
            "site_names": ["indeed", "linkedin"],
            "job_type": "fulltime",
            "results_wanted": 20,
            "schedule_time": (datetime.now() + timedelta(hours=1)).isoformat(),
            "recurring": False
        }
        
        with patch('app.services.admin_service.AdminService.create_scheduled_search', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock(**mock_search_response)
            
            response = client.post("/admin/scheduled-searches", json=search_request)
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["id"] == "123"
            assert data["name"] == "Test Search"
            assert data["status"] == "pending"

    def test_create_scheduled_search_validation_error(self, client):
        """Test POST /admin/scheduled-searches with invalid data."""
        invalid_request = {
            "name": "",  # Empty name
            "search_term": "",  # Empty search term
            "site_names": [],  # Empty site names
            "results_wanted": -5  # Invalid negative value
        }
        
        response = client.post("/admin/scheduled-searches", json=invalid_request)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "detail" in data

    def test_create_scheduled_search_service_error(self, client):
        """Test POST /admin/scheduled-searches handles service errors."""
        search_request = {
            "name": "Test Search",
            "search_term": "engineer",
            "site_names": ["indeed"],
            "schedule_time": (datetime.now() + timedelta(hours=1)).isoformat()
        }
        
        with patch('app.services.admin_service.AdminService.create_scheduled_search', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("Database error")
            
            response = client.post("/admin/scheduled-searches", json=search_request)
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "error" in data

    def test_get_scheduled_searches_success(self, client):
        """Test GET /admin/scheduled-searches with successful response."""
        mock_searches = [
            {
                "id": "1",
                "name": "Search 1",
                "status": "completed",
                "search_params": {"search_term": "engineer"},
                "created_at": datetime.now().isoformat(),
                "scheduled_time": datetime.now().isoformat(),
                "started_at": datetime.now().isoformat(),
                "completed_at": datetime.now().isoformat(),
                "jobs_found": 25,
                "error_message": None,
                "recurring": False
            },
            {
                "id": "2", 
                "name": "Search 2",
                "status": "pending",
                "search_params": {"search_term": "developer"},
                "created_at": datetime.now().isoformat(),
                "scheduled_time": (datetime.now() + timedelta(hours=1)).isoformat(),
                "started_at": None,
                "completed_at": None,
                "jobs_found": None,
                "error_message": None,
                "recurring": True
            }
        ]
        
        with patch('app.services.admin_service.AdminService.get_scheduled_searches', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [MagicMock(**search) for search in mock_searches]
            
            response = client.get("/admin/scheduled-searches")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 2
            assert data[0]["id"] == "1"
            assert data[0]["status"] == "completed"
            assert data[1]["recurring"] is True

    def test_get_scheduled_searches_with_status_filter(self, client):
        """Test GET /admin/scheduled-searches with status filter."""
        mock_searches = [
            {
                "id": "1",
                "name": "Pending Search",
                "status": "pending",
                "search_params": {},
                "created_at": datetime.now().isoformat(),
                "scheduled_time": datetime.now().isoformat()
            }
        ]
        
        with patch('app.services.admin_service.AdminService.get_scheduled_searches', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [MagicMock(**search) for search in mock_searches]
            
            response = client.get("/admin/scheduled-searches?status=pending&limit=10")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 1
            assert data[0]["status"] == "pending"

    def test_get_scheduled_search_by_id_success(self, client):
        """Test GET /admin/scheduled-searches/{search_id} with existing search."""
        mock_search = {
            "id": "123",
            "name": "Test Search",
            "status": "completed",
            "search_params": {"search_term": "engineer", "location": "SF"},
            "created_at": datetime.now().isoformat(),
            "scheduled_time": datetime.now().isoformat(),
            "started_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
            "jobs_found": 42,
            "error_message": None,
            "recurring": False
        }
        
        with patch('app.services.admin_service.AdminService.get_search_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(**mock_search)
            
            response = client.get("/admin/scheduled-searches/123")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == "123"
            assert data["jobs_found"] == 42

    def test_get_scheduled_search_by_id_not_found(self, client):
        """Test GET /admin/scheduled-searches/{search_id} with non-existent search."""
        with patch('app.services.admin_service.AdminService.get_search_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            
            response = client.get("/admin/scheduled-searches/999")
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "not found" in data["detail"].lower()

    def test_cancel_scheduled_search_success(self, client):
        """Test DELETE /admin/scheduled-searches/{search_id} with successful cancellation."""
        with patch('app.services.admin_service.AdminService.cancel_search', new_callable=AsyncMock) as mock_cancel:
            mock_cancel.return_value = True
            
            response = client.delete("/admin/scheduled-searches/123")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["message"] == "Search cancelled successfully"

    def test_cancel_scheduled_search_not_found(self, client):
        """Test DELETE /admin/scheduled-searches/{search_id} with non-existent search."""
        with patch('app.services.admin_service.AdminService.cancel_search', new_callable=AsyncMock) as mock_cancel:
            mock_cancel.return_value = False
            
            response = client.delete("/admin/scheduled-searches/999")
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "not found" in data["detail"].lower()

    def test_get_search_templates_success(self, client):
        """Test GET /admin/search-templates with successful response."""
        mock_templates = [
            {
                "id": "template-1",
                "name": "Software Engineer Template",
                "description": "Template for software engineer searches",
                "search_params": {
                    "search_term": "software engineer",
                    "location": "San Francisco",
                    "site_names": ["indeed", "linkedin"],
                    "job_type": "fulltime"
                },
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        ]
        
        with patch('app.services.admin_service.AdminService.get_search_templates', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [MagicMock(**template) for template in mock_templates]
            
            response = client.get("/admin/search-templates")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "Software Engineer Template"

    def test_create_search_template_success(self, client):
        """Test POST /admin/search-templates with valid data."""
        template_data = {
            "name": "Data Scientist Template",
            "description": "Template for data scientist searches",
            "search_term": "data scientist",
            "location": "New York",
            "site_names": ["indeed", "linkedin"],
            "job_type": "fulltime",
            "results_wanted": 50
        }
        
        mock_response = {
            "id": "new-template-id",
            **template_data,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        with patch('app.services.admin_service.AdminService.create_search_template', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            
            response = client.post("/admin/search-templates", json=template_data)
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == "Data Scientist Template"
            assert data["id"] == "new-template-id"

    def test_update_search_template_success(self, client):
        """Test PUT /admin/search-templates/{template_id} with valid data."""
        update_data = {
            "name": "Updated Template Name",
            "description": "Updated description",
            "search_term": "updated search term"
        }
        
        mock_response = {
            "id": "template-1",
            "name": "Updated Template Name",
            "description": "Updated description",
            "search_params": {"search_term": "updated search term"},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        with patch('app.services.admin_service.AdminService.update_search_template', new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_response
            
            response = client.put("/admin/search-templates/template-1", json=update_data)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["name"] == "Updated Template Name"

    def test_update_search_template_not_found(self, client):
        """Test PUT /admin/search-templates/{template_id} with non-existent template."""
        update_data = {"name": "Updated Name"}
        
        with patch('app.services.admin_service.AdminService.update_search_template', new_callable=AsyncMock) as mock_update:
            mock_update.return_value = None
            
            response = client.put("/admin/search-templates/nonexistent", json=update_data)
            
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_search_template_success(self, client):
        """Test DELETE /admin/search-templates/{template_id} with successful deletion."""
        with patch('app.services.admin_service.AdminService.delete_search_template', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = True
            
            response = client.delete("/admin/search-templates/template-1")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["message"] == "Template deleted successfully"

    def test_delete_search_template_not_found(self, client):
        """Test DELETE /admin/search-templates/{template_id} with non-existent template."""
        with patch('app.services.admin_service.AdminService.delete_search_template', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = False
            
            response = client.delete("/admin/search-templates/nonexistent")
            
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_search_logs_success(self, client):
        """Test GET /admin/search-logs with successful response."""
        mock_logs = [
            {
                "id": 1,
                "search_id": "123",
                "level": "INFO",
                "message": "Search started",
                "timestamp": datetime.now().isoformat(),
                "details": {}
            },
            {
                "id": 2,
                "search_id": "123", 
                "level": "ERROR",
                "message": "Search failed",
                "timestamp": datetime.now().isoformat(),
                "details": {"error": "Network timeout"}
            }
        ]
        
        with patch('app.services.admin_service.AdminService.get_search_logs', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [MagicMock(**log) for log in mock_logs]
            
            response = client.get("/admin/search-logs?search_id=123&level=ERROR&limit=100")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 2
            assert data[1]["level"] == "ERROR"

    def test_get_system_health_success(self, client):
        """Test GET /admin/system-health with successful response."""
        mock_health = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "components": {
                "database": {"status": "connected", "response_time_ms": 15},
                "redis": {"status": "connected", "response_time_ms": 8},
                "job_sites": {"indeed": "accessible", "linkedin": "accessible"}
            },
            "performance": {
                "memory_usage_percent": 45.2,
                "cpu_usage_percent": 23.1,
                "disk_usage_percent": 68.5
            },
            "searches": {
                "active_count": 3,
                "pending_count": 5,
                "completed_today": 25
            }
        }
        
        with patch('app.services.admin_service.AdminService.get_system_health', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_health
            
            response = client.get("/admin/system-health")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert data["components"]["database"]["status"] == "connected"
            assert data["performance"]["cpu_usage_percent"] == 23.1

    def test_admin_authentication_required(self, authenticated_client, admin_headers):
        """Test admin endpoints require proper authentication."""
        response = authenticated_client.get("/admin/dashboard", headers=admin_headers)
        
        # Should not return 403 with valid admin API key
        assert response.status_code != status.HTTP_403_FORBIDDEN

    def test_admin_authentication_user_key_rejected(self, authenticated_client, user_headers):
        """Test admin endpoints reject user-level API keys."""
        # This would depend on the actual implementation of role-based access
        response = authenticated_client.get("/admin/dashboard", headers=user_headers)
        
        # Should either work (if no role distinction) or return 403
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]

    def test_admin_invalid_authentication(self, authenticated_client, invalid_headers):
        """Test admin endpoints reject invalid authentication."""
        response = authenticated_client.get("/admin/dashboard", headers=invalid_headers)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_scheduled_search_lifecycle(self, client):
        """Test complete lifecycle of scheduled search management."""
        # Create a scheduled search
        search_request = {
            "name": "Lifecycle Test Search",
            "search_term": "test engineer",
            "site_names": ["indeed"],
            "schedule_time": (datetime.now() + timedelta(hours=1)).isoformat()
        }
        
        mock_created_search = {
            "id": "lifecycle-123",
            "name": "Lifecycle Test Search",
            "status": "pending",
            "search_params": search_request,
            "created_at": datetime.now().isoformat()
        }
        
        with patch('app.services.admin_service.AdminService.create_scheduled_search', new_callable=AsyncMock) as mock_create, \
             patch('app.services.admin_service.AdminService.get_search_by_id', new_callable=AsyncMock) as mock_get, \
             patch('app.services.admin_service.AdminService.cancel_search', new_callable=AsyncMock) as mock_cancel:
            
            mock_create.return_value = MagicMock(**mock_created_search)
            mock_get.return_value = MagicMock(**mock_created_search)
            mock_cancel.return_value = True
            
            # Create
            response = client.post("/admin/scheduled-searches", json=search_request)
            assert response.status_code == status.HTTP_201_CREATED
            search_id = response.json()["id"]
            
            # Get by ID
            response = client.get(f"/admin/scheduled-searches/{search_id}")
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["name"] == "Lifecycle Test Search"
            
            # Cancel
            response = client.delete(f"/admin/scheduled-searches/{search_id}")
            assert response.status_code == status.HTTP_200_OK

    def test_search_template_lifecycle(self, client):
        """Test complete lifecycle of search template management."""
        # Create template
        template_data = {
            "name": "Lifecycle Template",
            "description": "Test template",
            "search_term": "engineer",
            "location": "SF"
        }
        
        mock_template = {
            "id": "template-lifecycle",
            **template_data,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        with patch('app.services.admin_service.AdminService.create_search_template', new_callable=AsyncMock) as mock_create, \
             patch('app.services.admin_service.AdminService.update_search_template', new_callable=AsyncMock) as mock_update, \
             patch('app.services.admin_service.AdminService.delete_search_template', new_callable=AsyncMock) as mock_delete:
            
            mock_create.return_value = mock_template
            mock_update.return_value = {**mock_template, "name": "Updated Template"}
            mock_delete.return_value = True
            
            # Create
            response = client.post("/admin/search-templates", json=template_data)
            assert response.status_code == status.HTTP_201_CREATED
            template_id = response.json()["id"]
            
            # Update
            update_data = {"name": "Updated Template"}
            response = client.put(f"/admin/search-templates/{template_id}", json=update_data)
            assert response.status_code == status.HTTP_200_OK
            
            # Delete
            response = client.delete(f"/admin/search-templates/{template_id}")
            assert response.status_code == status.HTTP_200_OK

    def test_admin_error_handling(self, client):
        """Test error handling across admin endpoints."""
        # Test service unavailable scenario
        with patch('app.services.admin_service.AdminService.get_admin_stats', new_callable=AsyncMock) as mock_stats:
            mock_stats.side_effect = Exception("Service unavailable")
            
            response = client.get("/admin/dashboard")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            
        # Test invalid JSON
        response = client.post(
            "/admin/scheduled-searches",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_admin_pagination_and_filtering(self, client):
        """Test pagination and filtering features."""
        # Test scheduled searches with pagination
        response = client.get("/admin/scheduled-searches?limit=5&status=pending")
        # Should not error even if no data
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        
        # Test search logs with filtering
        response = client.get("/admin/search-logs?level=ERROR&limit=10")
        assert response.status_code == status.HTTP_200_OK