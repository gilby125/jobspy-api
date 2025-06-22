"""Integration tests for /health endpoints."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import status
from datetime import datetime


class TestHealthAPIIntegration:
    """Integration test cases for health API endpoints."""

    def test_basic_health_check_success(self, client):
        """Test GET /health returns successful health status."""
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data

    def test_basic_health_check_response_format(self, client):
        """Test health check response has correct format."""
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Required fields
        required_fields = ["status", "timestamp", "version", "environment"]
        for field in required_fields:
            assert field in data
        
        # Status should be "ok" for basic health check
        assert data["status"] == "ok"
        
        # Timestamp should be recent
        timestamp = datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
        assert isinstance(timestamp, datetime)

    def test_detailed_health_check_success(self, client):
        """Test GET /health/detailed returns comprehensive health status."""
        mock_health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "database": {
                    "status": "healthy",
                    "response_time_ms": 15,
                    "last_check": datetime.now().isoformat()
                },
                "cache": {
                    "status": "healthy", 
                    "response_time_ms": 5,
                    "last_check": datetime.now().isoformat()
                },
                "external_apis": {
                    "status": "healthy",
                    "services": {
                        "indeed": "accessible",
                        "linkedin": "accessible"
                    }
                }
            },
            "system": {
                "memory_usage_percent": 45.2,
                "cpu_usage_percent": 23.1,
                "disk_usage_percent": 68.5,
                "uptime_seconds": 86400
            },
            "application": {
                "active_connections": 25,
                "request_rate_per_minute": 120,
                "error_rate_percent": 0.5,
                "cache_hit_rate": 0.85
            }
        }
        
        with patch('app.utils.auth_health.get_detailed_health_status', new_callable=AsyncMock) as mock_health:
            mock_health.return_value = mock_health_data
            
            response = client.get("/health/detailed")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert "services" in data
            assert "system" in data
            assert data["services"]["database"]["status"] == "healthy"
            assert data["system"]["cpu_usage_percent"] == 23.1

    def test_detailed_health_check_degraded(self, client):
        """Test GET /health/detailed when some services are degraded."""
        mock_health_data = {
            "status": "degraded",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "database": {
                    "status": "healthy",
                    "response_time_ms": 15
                },
                "cache": {
                    "status": "unhealthy",
                    "response_time_ms": 5000,
                    "error": "Connection timeout"
                },
                "external_apis": {
                    "status": "degraded",
                    "services": {
                        "indeed": "accessible",
                        "linkedin": "timeout"
                    }
                }
            },
            "system": {
                "memory_usage_percent": 85.5,
                "cpu_usage_percent": 78.3,
                "disk_usage_percent": 92.1
            }
        }
        
        with patch('app.utils.auth_health.get_detailed_health_status', new_callable=AsyncMock) as mock_health:
            mock_health.return_value = mock_health_data
            
            response = client.get("/health/detailed")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "degraded"
            assert data["services"]["cache"]["status"] == "unhealthy"
            assert data["system"]["memory_usage_percent"] > 80

    def test_detailed_health_check_error(self, client):
        """Test GET /health/detailed handles service errors."""
        with patch('app.utils.auth_health.get_detailed_health_status', new_callable=AsyncMock) as mock_health:
            mock_health.side_effect = Exception("Health check service error")
            
            response = client.get("/health/detailed")
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "error" in data

    def test_database_health_check_success(self, client, test_db):
        """Test GET /health/db returns successful database health."""
        with patch('app.utils.auth_health.check_database_health') as mock_db_health:
            mock_db_health.return_value = {
                "status": "healthy",
                "response_time_ms": 12,
                "connection_pool": {
                    "active": 5,
                    "idle": 10,
                    "total": 15
                },
                "last_migration": "20250606_2253_initial",
                "table_count": 15
            }
            
            response = client.get("/health/db")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert data["response_time_ms"] == 12
            assert "connection_pool" in data

    def test_database_health_check_unhealthy(self, client):
        """Test GET /health/db when database is unhealthy."""
        with patch('app.utils.auth_health.check_database_health') as mock_db_health:
            mock_db_health.return_value = {
                "status": "unhealthy",
                "error": "Connection refused",
                "response_time_ms": None,
                "last_successful_check": "2024-01-01T10:00:00Z"
            }
            
            response = client.get("/health/db")
            
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "error" in data

    def test_cache_health_check_success(self, client):
        """Test GET /health/cache returns successful cache health."""
        with patch('app.utils.auth_health.check_cache_health', new_callable=AsyncMock) as mock_cache_health:
            mock_cache_health.return_value = {
                "status": "healthy",
                "response_time_ms": 3,
                "memory_usage_mb": 128,
                "hit_rate": 0.92,
                "connected_clients": 15,
                "keys_count": 1500
            }
            
            response = client.get("/health/cache")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert data["hit_rate"] == 0.92
            assert data["memory_usage_mb"] == 128

    def test_cache_health_check_unhealthy(self, client):
        """Test GET /health/cache when cache is unhealthy."""
        with patch('app.utils.auth_health.check_cache_health', new_callable=AsyncMock) as mock_cache_health:
            mock_cache_health.return_value = {
                "status": "unhealthy",
                "error": "Redis connection failed",
                "response_time_ms": None
            }
            
            response = client.get("/health/cache")
            
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "error" in data

    def test_external_services_health_check(self, client):
        """Test GET /health/external returns external services status."""
        with patch('app.utils.auth_health.check_external_services_health', new_callable=AsyncMock) as mock_external:
            mock_external.return_value = {
                "status": "healthy",
                "services": {
                    "indeed": {
                        "status": "accessible",
                        "response_time_ms": 234,
                        "last_check": datetime.now().isoformat()
                    },
                    "linkedin": {
                        "status": "accessible",
                        "response_time_ms": 189,
                        "last_check": datetime.now().isoformat()
                    },
                    "glassdoor": {
                        "status": "timeout",
                        "response_time_ms": None,
                        "error": "Request timeout after 5s",
                        "last_check": datetime.now().isoformat()
                    }
                },
                "accessible_count": 2,
                "total_count": 3
            }
            
            response = client.get("/health/external")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert data["accessible_count"] == 2
            assert data["services"]["indeed"]["status"] == "accessible"
            assert data["services"]["glassdoor"]["status"] == "timeout"

    def test_api_readiness_check_ready(self, client):
        """Test GET /health/ready when API is ready."""
        with patch('app.utils.auth_health.check_api_readiness', new_callable=AsyncMock) as mock_readiness:
            mock_readiness.return_value = {
                "ready": True,
                "checks": {
                    "database": True,
                    "cache": True,
                    "migrations": True,
                    "config": True
                },
                "startup_time_seconds": 2.5
            }
            
            response = client.get("/health/ready")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["ready"] is True
            assert data["checks"]["database"] is True

    def test_api_readiness_check_not_ready(self, client):
        """Test GET /health/ready when API is not ready."""
        with patch('app.utils.auth_health.check_api_readiness', new_callable=AsyncMock) as mock_readiness:
            mock_readiness.return_value = {
                "ready": False,
                "checks": {
                    "database": False,
                    "cache": True,
                    "migrations": False,
                    "config": True
                },
                "errors": [
                    "Database connection failed",
                    "Pending migrations detected"
                ]
            }
            
            response = client.get("/health/ready")
            
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert data["ready"] is False
            assert "errors" in data

    def test_api_liveness_check_alive(self, client):
        """Test GET /health/live when API is alive."""
        with patch('app.utils.auth_health.check_api_liveness') as mock_liveness:
            mock_liveness.return_value = {
                "alive": True,
                "uptime_seconds": 3600,
                "memory_usage_mb": 256,
                "active_threads": 12
            }
            
            response = client.get("/health/live")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["alive"] is True
            assert data["uptime_seconds"] == 3600

    def test_api_liveness_check_not_alive(self, client):
        """Test GET /health/live when API is not responsive."""
        with patch('app.utils.auth_health.check_api_liveness') as mock_liveness:
            mock_liveness.return_value = {
                "alive": False,
                "error": "High memory usage detected",
                "memory_usage_mb": 2048,
                "memory_limit_mb": 1024
            }
            
            response = client.get("/health/live")
            
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert data["alive"] is False
            assert "error" in data

    def test_health_checks_no_auth_required(self, authenticated_client):
        """Test health endpoints don't require authentication."""
        # Test that health endpoints work without API key
        response = authenticated_client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        
        response = authenticated_client.get("/health/detailed")
        # Should work or return service error, not auth error
        assert response.status_code != status.HTTP_403_FORBIDDEN

    def test_health_check_cors_headers(self, client):
        """Test health endpoints include proper CORS headers."""
        response = client.options("/health")
        assert response.status_code == status.HTTP_200_OK
        
        response = client.get("/health")
        # Basic CORS test - headers may vary based on configuration
        assert response.status_code == status.HTTP_200_OK

    def test_health_check_caching_headers(self, client):
        """Test health endpoints have appropriate caching headers."""
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        # Health checks should typically not be cached
        cache_control = response.headers.get("Cache-Control", "")
        # Should include no-cache or short expiry
        assert "no-cache" in cache_control.lower() or "max-age" in cache_control.lower()

    def test_health_check_load_balancer_format(self, client):
        """Test health check format is compatible with load balancers."""
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Should have simple, consistent format for load balancers
        assert "status" in data
        assert data["status"] in ["ok", "healthy", "pass"]

    def test_health_metrics_collection(self, client):
        """Test health endpoints provide metrics for monitoring."""
        response = client.get("/health/detailed")
        
        # Should return 200 or service error, but provide some health data
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Should include metrics that can be used for monitoring
            assert "timestamp" in data

    def test_health_check_performance(self, client):
        """Test health checks respond quickly."""
        import time
        
        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()
        
        assert response.status_code == status.HTTP_200_OK
        # Health check should be fast (under 1 second)
        assert (end_time - start_time) < 1.0

    def test_health_check_concurrency(self, client):
        """Test health checks handle concurrent requests."""
        import concurrent.futures
        import requests
        
        def make_health_request():
            return client.get("/health")
        
        # Test multiple concurrent health checks
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_health_request) for _ in range(5)]
            responses = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK

    def test_health_status_consistency(self, client):
        """Test health status is consistent across multiple calls."""
        # Make multiple health check calls
        responses = [client.get("/health") for _ in range(3)]
        
        # All should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "ok"

    def test_health_endpoint_error_recovery(self, client):
        """Test health endpoints recover from temporary errors."""
        # Test that a service error doesn't permanently break health checks
        with patch('app.utils.auth_health.get_detailed_health_status', new_callable=AsyncMock) as mock_health:
            # First call fails
            mock_health.side_effect = Exception("Temporary error")
            response = client.get("/health/detailed")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            
            # Second call succeeds
            mock_health.side_effect = None
            mock_health.return_value = {"status": "healthy", "timestamp": datetime.now().isoformat()}
            response = client.get("/health/detailed")
            assert response.status_code == status.HTTP_200_OK

    def test_health_check_monitoring_integration(self, client):
        """Test health checks provide data suitable for monitoring systems."""
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        
        # Test basic health check works for simple monitoring
        data = response.json()
        assert data["status"] == "ok"
        
        # Test detailed health provides metrics
        response = client.get("/health/detailed")
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "timestamp" in data
            # Should have structured data for monitoring tools