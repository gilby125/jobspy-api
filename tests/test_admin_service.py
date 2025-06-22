"""Unit tests for AdminService."""
import pytest
import json
import psutil
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.admin_service import AdminService
from app.models.admin_models import (
    ScheduledSearchRequest, ScheduledSearchResponse, AdminStats,
    SearchTemplate, SearchLog, SearchStatus
)


class TestAdminService:
    """Test cases for AdminService class."""

    @pytest.fixture
    def admin_service(self, test_db):
        """Create AdminService instance with test database."""
        return AdminService(test_db)

    @pytest.fixture
    def sample_search_request(self):
        """Sample scheduled search request."""
        return ScheduledSearchRequest(
            name="Test Search",
            search_term="software engineer",
            location="San Francisco",
            site_names=["indeed", "linkedin"],
            job_type="fulltime",
            results_wanted=20,
            schedule_time=datetime.now() + timedelta(hours=1),
            recurring=False
        )

    @pytest.mark.asyncio
    async def test_get_admin_stats_success(self, admin_service, test_db):
        """Test successful retrieval of admin stats."""
        # Set up database with test data
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Insert test data
        test_db.execute(text("""
            CREATE TABLE IF NOT EXISTS scraping_runs (
                id SERIAL PRIMARY KEY,
                source_platform TEXT,
                search_terms TEXT[],
                locations TEXT[],
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                status TEXT,
                jobs_found INTEGER,
                config_used TEXT
            )
        """))
        
        test_db.execute(text("""
            INSERT INTO scraping_runs (source_platform, start_time, status, jobs_found)
            VALUES 
                ('indeed', :today, 'completed', 25),
                ('linkedin', :yesterday, 'completed', 15),
                ('glassdoor', :today, 'failed', 0),
                ('indeed', :today, 'running', 0)
        """), {
            'today': today_start + timedelta(hours=2),
            'yesterday': today_start - timedelta(days=1)
        })
        test_db.commit()

        with patch.object(admin_service, '_get_cache_hit_rate', return_value=0.85), \
             patch.object(admin_service, '_check_system_health', return_value={"api": "healthy", "database": "healthy"}):
            
            stats = await admin_service.get_admin_stats()
            
            assert isinstance(stats, AdminStats)
            assert stats.total_searches == 4
            assert stats.searches_today == 3
            assert stats.active_searches == 1
            assert stats.failed_searches_today == 1
            assert stats.cache_hit_rate == 0.85
            assert stats.system_health["api"] == "healthy"

    @pytest.mark.asyncio
    async def test_get_admin_stats_database_error(self, admin_service):
        """Test get_admin_stats handles database errors gracefully."""
        with patch.object(admin_service.db, 'execute', side_effect=Exception("Database error")):
            stats = await admin_service.get_admin_stats()
            
            # Should return stats with zero values
            assert isinstance(stats, AdminStats)
            assert stats.total_searches == 0
            assert stats.searches_today == 0
            assert stats.active_searches == 0

    @pytest.mark.asyncio
    async def test_check_system_health_all_healthy(self, admin_service):
        """Test system health check when all components are healthy."""
        with patch.object(admin_service.db, 'execute'), \
             patch('app.cache.cache.set', new_callable=AsyncMock), \
             patch('app.cache.cache.get', new_callable=AsyncMock, return_value="test"):
            
            health = await admin_service._check_system_health()
            
            assert health["database"] == "healthy"
            assert health["cache"] == "healthy"
            assert health["api"] == "healthy"

    @pytest.mark.asyncio
    async def test_check_system_health_database_unhealthy(self, admin_service):
        """Test system health check when database is unhealthy."""
        with patch.object(admin_service.db, 'execute', side_effect=Exception("DB Error")), \
             patch('app.cache.cache.set', new_callable=AsyncMock), \
             patch('app.cache.cache.get', new_callable=AsyncMock, return_value="test"):
            
            health = await admin_service._check_system_health()
            
            assert health["database"] == "unhealthy"
            assert health["cache"] == "healthy"
            assert health["api"] == "healthy"

    @pytest.mark.asyncio
    async def test_check_system_health_cache_unhealthy(self, admin_service):
        """Test system health check when cache is unhealthy."""
        with patch.object(admin_service.db, 'execute'), \
             patch('app.cache.cache.set', side_effect=Exception("Cache Error")):
            
            health = await admin_service._check_system_health()
            
            assert health["database"] == "healthy"
            assert health["cache"] == "unhealthy"
            assert health["api"] == "healthy"

    @pytest.mark.asyncio
    async def test_create_scheduled_search_success(self, admin_service, test_db, sample_search_request):
        """Test successful creation of scheduled search."""
        # Mock database insertion
        mock_result = MagicMock()
        mock_result.fetchone.return_value = [123]  # Mock database ID
        
        with patch.object(test_db, 'execute', return_value=mock_result), \
             patch.object(test_db, 'commit'):
            
            response = await admin_service.create_scheduled_search("test-id", sample_search_request)
            
            assert isinstance(response, ScheduledSearchResponse)
            assert response.id == "123"
            assert response.name == "Test Search"
            assert response.status == SearchStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_scheduled_search_database_error(self, admin_service, test_db, sample_search_request):
        """Test create_scheduled_search handles database errors."""
        with patch.object(test_db, 'execute', side_effect=Exception("DB Error")), \
             patch.object(test_db, 'rollback') as mock_rollback:
            
            with pytest.raises(Exception, match="DB Error"):
                await admin_service.create_scheduled_search("test-id", sample_search_request)
            
            mock_rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_scheduled_searches_success(self, admin_service, test_db):
        """Test successful retrieval of scheduled searches."""
        # Mock database query result
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.id = 1
        mock_row.source_platform = "indeed"
        mock_row.search_terms = ["software"]
        mock_row.locations = ["SF"]
        mock_row.start_time = datetime.now()
        mock_row.end_time = None
        mock_row.status = "completed"
        mock_row.jobs_found = 25
        mock_row.config_used = '{"name": "Test Search"}'
        mock_row.created_at = datetime.now()
        
        mock_result.fetchall.return_value = [mock_row]
        
        with patch.object(test_db, 'execute', return_value=mock_result):
            searches = await admin_service.get_scheduled_searches()
            
            assert len(searches) == 1
            assert isinstance(searches[0], ScheduledSearchResponse)
            assert searches[0].id == "1"
            assert searches[0].name == "Test Search"
            assert searches[0].status == SearchStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_scheduled_searches_with_status_filter(self, admin_service, test_db):
        """Test get_scheduled_searches with status filter."""
        # Mock multiple search results with different statuses
        mock_result = MagicMock()
        mock_row1 = MagicMock()
        mock_row1.id = 1
        mock_row1.status = "completed"
        mock_row1.config_used = '{}'
        mock_row1.start_time = datetime.now()
        mock_row1.end_time = datetime.now()
        mock_row1.jobs_found = 25
        mock_row1.created_at = datetime.now()
        
        mock_row2 = MagicMock()
        mock_row2.id = 2
        mock_row2.status = "failed"
        mock_row2.config_used = '{}'
        mock_row2.start_time = datetime.now()
        mock_row2.end_time = datetime.now()
        mock_row2.jobs_found = 0
        mock_row2.created_at = datetime.now()
        
        mock_result.fetchall.return_value = [mock_row1, mock_row2]
        
        with patch.object(test_db, 'execute', return_value=mock_result):
            # Filter for completed searches only
            searches = await admin_service.get_scheduled_searches(status=SearchStatus.COMPLETED)
            
            assert len(searches) == 1
            assert searches[0].status == SearchStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_scheduled_searches_database_error(self, admin_service, test_db):
        """Test get_scheduled_searches handles database errors."""
        with patch.object(test_db, 'execute', side_effect=Exception("DB Error")):
            searches = await admin_service.get_scheduled_searches()
            
            assert searches == []

    @pytest.mark.asyncio
    async def test_get_search_by_id_success(self, admin_service, test_db):
        """Test successful retrieval of search by ID."""
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.id = 123
        mock_row.source_platform = "indeed"
        mock_row.start_time = datetime.now()
        mock_row.end_time = datetime.now()
        mock_row.status = "completed"
        mock_row.jobs_found = 25
        mock_row.config_used = '{"name": "Test Search"}'
        mock_row.created_at = datetime.now()
        
        mock_result.fetchone.return_value = mock_row
        
        with patch.object(test_db, 'execute', return_value=mock_result):
            search = await admin_service.get_search_by_id("123")
            
            assert isinstance(search, ScheduledSearchResponse)
            assert search.id == "123"
            assert search.name == "Test Search"
            assert search.status == SearchStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_search_by_id_not_found(self, admin_service, test_db):
        """Test get_search_by_id when search not found."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        
        with patch.object(test_db, 'execute', return_value=mock_result):
            search = await admin_service.get_search_by_id("999")
            
            assert search is None

    @pytest.mark.asyncio
    async def test_get_search_by_id_invalid_id(self, admin_service):
        """Test get_search_by_id with invalid ID format."""
        search = await admin_service.get_search_by_id("invalid-id")
        assert search is None

    @pytest.mark.asyncio
    async def test_cancel_search_success(self, admin_service, test_db):
        """Test successful search cancellation."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        
        with patch.object(test_db, 'execute', return_value=mock_result), \
             patch.object(test_db, 'commit'):
            
            result = await admin_service.cancel_search("123")
            assert result is True

    @pytest.mark.asyncio
    async def test_cancel_search_not_found(self, admin_service, test_db):
        """Test cancel search when search not found or not cancellable."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        
        with patch.object(test_db, 'execute', return_value=mock_result), \
             patch.object(test_db, 'commit'):
            
            result = await admin_service.cancel_search("999")
            assert result is False

    @pytest.mark.asyncio
    async def test_cancel_search_invalid_id(self, admin_service):
        """Test cancel search with invalid ID."""
        result = await admin_service.cancel_search("invalid-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_search_database_error(self, admin_service, test_db):
        """Test cancel search handles database errors."""
        with patch.object(test_db, 'execute', side_effect=Exception("DB Error")), \
             patch.object(test_db, 'rollback') as mock_rollback:
            
            result = await admin_service.cancel_search("123")
            
            assert result is False
            mock_rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_search_status_success(self, admin_service, test_db):
        """Test successful search status update."""
        with patch.object(test_db, 'execute'), \
             patch.object(test_db, 'commit'):
            
            await admin_service.update_search_status(
                "123", SearchStatus.COMPLETED, jobs_found=25
            )
            
            # Should complete without error
            assert True

    @pytest.mark.asyncio
    async def test_update_search_status_with_error(self, admin_service, test_db):
        """Test search status update with error message."""
        with patch.object(test_db, 'execute'), \
             patch.object(test_db, 'commit'):
            
            await admin_service.update_search_status(
                "123", SearchStatus.FAILED, error_message="Scraping failed"
            )
            
            # Should complete without error
            assert True

    @pytest.mark.asyncio
    async def test_update_search_status_invalid_id(self, admin_service):
        """Test update search status with invalid ID."""
        # Should not raise exception, just log error
        await admin_service.update_search_status(
            "invalid", SearchStatus.COMPLETED
        )
        assert True

    @pytest.mark.asyncio
    async def test_create_search_template_success(self, admin_service):
        """Test successful search template creation."""
        template_data = {
            "name": "Software Engineer Template",
            "description": "Template for software engineer searches",
            "search_term": "software engineer",
            "location": "San Francisco",
            "site_names": ["indeed", "linkedin"],
            "results_wanted": 50
        }
        
        with patch('app.cache.cache.set', new_callable=AsyncMock), \
             patch('app.cache.cache.get', new_callable=AsyncMock, return_value=[]):
            
            result = await admin_service.create_search_template(template_data)
            
            assert isinstance(result, dict)
            assert result["name"] == "Software Engineer Template"
            assert "id" in result

    @pytest.mark.asyncio
    async def test_get_search_templates_success(self, admin_service):
        """Test successful retrieval of search templates."""
        template_data = {
            "id": "template-1",
            "name": "Test Template",
            "description": "Test description",
            "search_params": {"search_term": "test"},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        with patch('app.cache.cache.get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [["template-1"], template_data]
            
            templates = await admin_service.get_search_templates()
            
            assert len(templates) == 1
            assert isinstance(templates[0], SearchTemplate)

    @pytest.mark.asyncio
    async def test_delete_search_template_success(self, admin_service):
        """Test successful search template deletion."""
        with patch('app.cache.cache.get', new_callable=AsyncMock, return_value={"name": "Test"}), \
             patch('app.cache.cache.delete', new_callable=AsyncMock), \
             patch('app.cache.cache.set', new_callable=AsyncMock):
            
            result = await admin_service.delete_search_template("template-1")
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_search_template_not_found(self, admin_service):
        """Test delete search template when template not found."""
        with patch('app.cache.cache.get', new_callable=AsyncMock, return_value=None):
            result = await admin_service.delete_search_template("nonexistent")
            assert result is False

    @pytest.mark.asyncio
    async def test_update_search_template_success(self, admin_service):
        """Test successful search template update."""
        existing_template = {
            "id": "template-1",
            "name": "Old Name",
            "description": "Old description",
            "search_params": {"search_term": "old term"},
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        update_data = {
            "name": "New Name",
            "search_term": "new term"
        }
        
        with patch('app.cache.cache.get', new_callable=AsyncMock, return_value=existing_template), \
             patch('app.cache.cache.set', new_callable=AsyncMock):
            
            result = await admin_service.update_search_template("template-1", update_data)
            
            assert result is not None
            assert result["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_update_search_template_not_found(self, admin_service):
        """Test update search template when template not found."""
        with patch('app.cache.cache.get', new_callable=AsyncMock, return_value=None):
            result = await admin_service.update_search_template("nonexistent", {})
            assert result is None

    @pytest.mark.asyncio
    async def test_get_cache_hit_rate(self, admin_service):
        """Test cache hit rate calculation."""
        with patch('app.cache.cache.set', new_callable=AsyncMock), \
             patch('app.cache.cache.get', new_callable=AsyncMock, return_value="test"):
            
            hit_rate = await admin_service._get_cache_hit_rate()
            
            assert isinstance(hit_rate, float)
            assert 0.0 <= hit_rate <= 1.0

    @pytest.mark.asyncio
    async def test_get_cache_hit_rate_error(self, admin_service):
        """Test cache hit rate calculation handles errors."""
        with patch('app.cache.cache.set', side_effect=Exception("Cache Error")):
            hit_rate = await admin_service._get_cache_hit_rate()
            assert hit_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_system_performance(self, admin_service):
        """Test system performance metrics."""
        with patch('psutil.cpu_percent', return_value=45.5), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            mock_memory.return_value.percent = 60.2
            mock_disk.return_value.used = 500 * 1024**3  # 500 GB
            mock_disk.return_value.total = 1000 * 1024**3  # 1 TB
            
            performance = await admin_service._get_system_performance()
            
            assert performance["cpu_usage_percent"] == 45.5
            assert performance["memory_usage_percent"] == 60.2
            assert performance["disk_usage_percent"] == 50.0

    @pytest.mark.asyncio
    async def test_get_system_performance_error(self, admin_service):
        """Test system performance handles errors."""
        with patch('psutil.cpu_percent', side_effect=Exception("System Error")):
            performance = await admin_service._get_system_performance()
            
            assert performance["cpu_usage_percent"] == 0
            assert performance["memory_usage_percent"] == 0
            assert performance["disk_usage_percent"] == 0

    @pytest.mark.asyncio
    async def test_get_search_statistics(self, admin_service, test_db):
        """Test search statistics retrieval."""
        mock_result = MagicMock()
        mock_result.scalar.side_effect = [2, 1, 5]  # active, pending, completed
        
        with patch.object(test_db, 'execute', return_value=mock_result):
            stats = await admin_service._get_search_statistics()
            
            assert stats["active_count"] == 2
            assert stats["pending_count"] == 1
            assert stats["completed_today"] == 5

    @pytest.mark.asyncio
    async def test_get_search_statistics_error(self, admin_service, test_db):
        """Test search statistics handles database errors."""
        with patch.object(test_db, 'execute', side_effect=Exception("DB Error")):
            stats = await admin_service._get_search_statistics()
            
            assert stats["active_count"] == 0
            assert stats["pending_count"] == 0
            assert stats["completed_today"] == 0

    @pytest.mark.asyncio
    async def test_check_job_sites_accessibility(self, admin_service):
        """Test job sites accessibility check."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            results = await admin_service._check_job_sites_accessibility()
            
            assert isinstance(results, dict)
            assert "indeed" in results
            assert "linkedin" in results
            assert "glassdoor" in results

    @pytest.mark.asyncio
    async def test_check_job_sites_accessibility_timeout(self, admin_service):
        """Test job sites accessibility check with timeout."""
        with patch('asyncio.wait_for', side_effect=Exception("Timeout")):
            results = await admin_service._check_job_sites_accessibility()
            
            # Should return some results even on timeout
            assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_get_system_health_comprehensive(self, admin_service, test_db):
        """Test comprehensive system health check."""
        with patch.object(admin_service, '_get_system_performance', return_value={"cpu_usage_percent": 50}), \
             patch.object(admin_service, '_get_search_statistics', return_value={"active_count": 2}), \
             patch.object(admin_service, '_check_job_sites_accessibility', return_value={"indeed": "accessible"}), \
             patch.object(test_db, 'execute'), \
             patch('app.cache.cache.set', new_callable=AsyncMock), \
             patch('app.cache.cache.get', new_callable=AsyncMock, return_value="test"):
            
            health = await admin_service.get_system_health()
            
            assert health["status"] == "healthy"
            assert "components" in health
            assert "performance" in health
            assert "searches" in health
            assert "timestamp" in health

    @pytest.mark.asyncio
    async def test_schedule_search_task(self, admin_service, test_db):
        """Test scheduling a search task."""
        schedule_time = datetime.now() + timedelta(hours=1)
        search_params = {"search_term": "test", "location": "SF"}
        
        with patch.object(test_db, 'execute'), \
             patch.object(test_db, 'commit'):
            
            await admin_service.schedule_search_task("123", schedule_time, search_params)
            
            # Should complete without error
            assert True

    @pytest.mark.asyncio
    async def test_schedule_search_task_invalid_id(self, admin_service):
        """Test schedule search task with invalid ID."""
        schedule_time = datetime.now() + timedelta(hours=1)
        
        # Should not raise exception, just log error
        await admin_service.schedule_search_task("invalid", schedule_time, {})
        assert True