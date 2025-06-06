import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_api_key
# from app.db.database import get_db  # Temporarily disabled due to dependency issues
# Temporarily disable complex model imports
# from app.models.admin_models import (
#     ScheduledSearchRequest, ScheduledSearchResponse, AdminStats,
#     BulkSearchRequest, SearchTemplate, SystemConfig, SearchLog, SearchStatus
# )
# from app.services.admin_service import AdminService
# from app.services.background_service import background_service
from app.cache import cache
from app.config import settings

router = APIRouter()

def get_admin_user(api_key: str = Depends(get_api_key)):
    """Verify admin permissions for API key"""
    # In a real implementation, you'd check admin permissions here
    # For now, we'll assume all valid API keys have admin access
    return {"username": "admin", "role": "admin"}

@router.get("/login", response_class=HTMLResponse)
async def admin_login():
    """Admin login page with API key input"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>JobSpy Admin - Login</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); height: 100vh; display: flex; align-items: center; justify-content: center; }
            .login-container { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); max-width: 400px; width: 100%; }
            .logo { text-align: center; margin-bottom: 30px; }
            .logo h1 { color: #2c3e50; margin: 0; font-size: 28px; }
            .logo p { color: #7f8c8d; margin: 5px 0 0 0; }
            .form-group { margin-bottom: 20px; }
            .form-group label { display: block; margin-bottom: 5px; color: #2c3e50; font-weight: bold; }
            .form-group input { width: 100%; padding: 12px; border: 2px solid #ecf0f1; border-radius: 5px; font-size: 16px; box-sizing: border-box; }
            .form-group input:focus { outline: none; border-color: #3498db; }
            .login-btn { width: 100%; padding: 12px; background: #3498db; color: white; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; transition: background 0.3s; }
            .login-btn:hover { background: #2980b9; }
            .error { color: #e74c3c; margin-top: 10px; padding: 10px; background: #fadbd8; border-radius: 5px; display: none; }
            .hint { font-size: 12px; color: #7f8c8d; margin-top: 5px; }
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="logo">
                <h1>🔧 JobSpy Admin</h1>
                <p>Enter your API key to access the admin panel</p>
            </div>
            
            <form id="login-form">
                <div class="form-group">
                    <label for="api-key">API Key:</label>
                    <input type="password" id="api-key" placeholder="Enter your API key" required>
                    <div class="hint">The API key is required to access admin features</div>
                </div>
                
                <button type="submit" class="login-btn">Login to Admin Panel</button>
                
                <div id="error-message" class="error"></div>
            </form>
        </div>

        <script>
            // Store API key and redirect to dashboard
            document.getElementById('login-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const apiKey = document.getElementById('api-key').value;
                const errorDiv = document.getElementById('error-message');
                
                // Test API key by making a request to dashboard
                try {
                    const response = await fetch('/admin/', {
                        headers: {
                            'x-api-key': apiKey
                        }
                    });
                    
                    if (response.ok) {
                        // Store API key in sessionStorage
                        sessionStorage.setItem('admin-api-key', apiKey);
                        // Redirect to dashboard
                        window.location.href = '/admin/';
                    } else {
                        errorDiv.textContent = 'Invalid API key. Please check and try again.';
                        errorDiv.style.display = 'block';
                    }
                } catch (error) {
                    errorDiv.textContent = 'Error connecting to server. Please try again.';
                    errorDiv.style.display = 'block';
                }
            });
        </script>
    </body>
    </html>
    """
    return html_content

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(admin_user: dict = Depends(get_admin_user)):
    """Admin dashboard main page"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>JobSpy Admin Panel</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
            .stat-card { background: #3498db; color: white; padding: 20px; border-radius: 8px; text-align: center; }
            .actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }
            .action-card { background: #27ae60; color: white; padding: 20px; border-radius: 8px; text-align: center; text-decoration: none; }
            .action-card:hover { background: #219a52; }
            button { background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
            button:hover { background: #2980b9; }
            .form-group { margin: 10px 0; }
            input, select, textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
            .search-form { background: #ecf0f1; padding: 20px; border-radius: 8px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔧 JobSpy Admin Panel</h1>
                <p>Manage job searches, monitor system health, and configure settings</p>
            </div>
            
            <div class="card">
                <h2>📊 Quick Stats</h2>
                <div class="stats">
                    <div class="stat-card">
                        <h3 id="total-searches">-</h3>
                        <p>Total Searches</p>
                    </div>
                    <div class="stat-card">
                        <h3 id="jobs-found">-</h3>
                        <p>Jobs Found Today</p>
                    </div>
                    <div class="stat-card">
                        <h3 id="active-searches">-</h3>
                        <p>Active Searches</p>
                    </div>
                    <div class="stat-card">
                        <h3 id="system-health">-</h3>
                        <p>System Health</p>
                    </div>
                </div>
            </div>

            <div class="card">
                <h2>🚀 Quick Actions</h2>
                <div class="actions">
                    <a href="/admin/searches" class="action-card">
                        <h3>📋 Manage Searches</h3>
                        <p>View, schedule, and monitor job searches</p>
                    </a>
                    <a href="/admin/templates" class="action-card">
                        <h3>📄 Search Templates</h3>
                        <p>Create and manage search templates</p>
                    </a>
                    <a href="/admin/analytics" class="action-card">
                        <h3>📈 Analytics</h3>
                        <p>View detailed analytics and reports</p>
                    </a>
                    <a href="/admin/settings" class="action-card">
                        <h3>⚙️ System Settings</h3>
                        <p>Configure system parameters</p>
                    </a>
                </div>
            </div>

            <div class="card">
                <h2>🔍 Quick Search</h2>
                <div class="search-form">
                    <h3>Schedule New Job Search</h3>
                    <form id="quick-search-form">
                        <div class="form-group">
                            <label>Search Name:</label>
                            <input type="text" id="search-name" placeholder="e.g., Software Engineers SF" required>
                        </div>
                        <div class="form-group">
                            <label>Search Term:</label>
                            <input type="text" id="search-term" placeholder="e.g., software engineer" required>
                        </div>
                        <div class="form-group">
                            <label>Location:</label>
                            <input type="text" id="location" placeholder="e.g., San Francisco, CA">
                        </div>
                        <div class="form-group">
                            <label>Job Sites:</label>
                            <select id="sites" multiple>
                                <option value="indeed" selected>Indeed</option>
                                <option value="linkedin" selected>LinkedIn</option>
                                <option value="glassdoor">Glassdoor</option>
                                <option value="zip_recruiter">ZipRecruiter</option>
                                <option value="google">Google Jobs</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Results per Site:</label>
                            <input type="number" id="results-wanted" value="50" min="1" max="1000">
                        </div>
                        <button type="submit">🚀 Start Search</button>
                    </form>
                </div>
            </div>
        </div>

        <script>
            // Get API key from session storage
            const apiKey = sessionStorage.getItem('admin-api-key');
            if (!apiKey) {
                window.location.href = '/admin/login';
                return;
            }

            // Load stats
            async function loadStats() {
                try {
                    const response = await fetch('/admin/stats', {
                        headers: { 'x-api-key': apiKey }
                    });
                    const stats = await response.json();
                    document.getElementById('total-searches').textContent = stats.total_searches;
                    document.getElementById('jobs-found').textContent = stats.jobs_found_today;
                    document.getElementById('active-searches').textContent = stats.active_searches;
                    document.getElementById('system-health').textContent = stats.system_health.status || 'OK';
                } catch (error) {
                    console.error('Failed to load stats:', error);
                }
            }

            // Handle quick search form
            document.getElementById('quick-search-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = {
                    name: document.getElementById('search-name').value,
                    search_term: document.getElementById('search-term').value,
                    location: document.getElementById('location').value,
                    site_names: Array.from(document.getElementById('sites').selectedOptions).map(o => o.value),
                    results_wanted: parseInt(document.getElementById('results-wanted').value),
                    country_indeed: 'USA'
                };

                try {
                    const response = await fetch('/admin/searches', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'x-api-key': apiKey
                        },
                        body: JSON.stringify(formData)
                    });
                    
                    if (response.ok) {
                        alert('Search scheduled successfully!');
                        document.getElementById('quick-search-form').reset();
                        loadStats();
                    } else {
                        alert('Failed to schedule search');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    alert('Error scheduling search');
                }
            });

            // Load stats on page load
            loadStats();
            
            // Refresh stats every 30 seconds
            setInterval(loadStats, 30000);
        </script>
    </body>
    </html>
    """
    return html_content

@router.get("/stats")
async def get_admin_stats(
    admin_user: dict = Depends(get_admin_user)
):
    """Get admin dashboard statistics"""
    # Return mock stats since database is temporarily disabled
    return {
        "total_searches": 42,
        "jobs_found_today": 156,
        "active_searches": 3,
        "system_health": {"status": "OK"},
        "cache_stats": {"hits": 89, "misses": 11},
        "timestamp": "2025-06-06T17:50:00Z"
    }

@router.post("/searches")
async def schedule_search(
    admin_user: dict = Depends(get_admin_user)
):
    """Schedule a new job search"""
    # Return mock response since database is temporarily disabled
    return {
        "id": str(uuid.uuid4()),
        "status": "scheduled",
        "message": "Search scheduled successfully (mock response)",
        "created_at": datetime.now().isoformat()
    }

@router.get("/searches", response_model=List[ScheduledSearchResponse])
async def get_scheduled_searches(
    status: Optional[SearchStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=1000),
    admin_user: dict = Depends(get_admin_user),
# db: Session = Depends(get_db)  # Temporarily disabled
):
    """Get list of scheduled searches"""
    admin_service = AdminService(db)
    return await admin_service.get_scheduled_searches(status=status, limit=limit)

@router.get("/searches/{search_id}", response_model=ScheduledSearchResponse)
async def get_search_details(
    search_id: str,
    admin_user: dict = Depends(get_admin_user),
# db: Session = Depends(get_db)  # Temporarily disabled
):
    """Get details of a specific search"""
    admin_service = AdminService(db)
    search = await admin_service.get_search_by_id(search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    return search

@router.post("/searches/{search_id}/cancel")
async def cancel_search(
    search_id: str,
    admin_user: dict = Depends(get_admin_user),
# db: Session = Depends(get_db)  # Temporarily disabled
):
    """Cancel a scheduled or running search"""
    admin_service = AdminService(db)
    success = await admin_service.cancel_search(search_id)
    if not success:
        raise HTTPException(status_code=404, detail="Search not found or cannot be cancelled")
    return {"message": "Search cancelled successfully"}

@router.post("/searches/bulk", response_model=List[ScheduledSearchResponse])
async def schedule_bulk_searches(
    bulk_request: BulkSearchRequest,
    background_tasks: BackgroundTasks,
    admin_user: dict = Depends(get_admin_user),
# db: Session = Depends(get_db)  # Temporarily disabled
):
    """Schedule multiple searches at once"""
    admin_service = AdminService(db)
    results = []
    
    for search_request in bulk_request.searches:
        search_id = str(uuid.uuid4())
        search_record = await admin_service.create_scheduled_search(search_id, search_request)
        
        # Schedule background task
        background_tasks.add_task(
            background_service.execute_search,
            search_id,
            search_request.dict()
        )
        
        results.append(search_record)
    
    return results

@router.get("/templates", response_model=List[SearchTemplate])
async def get_search_templates(
    admin_user: dict = Depends(get_admin_user),
# db: Session = Depends(get_db)  # Temporarily disabled
):
    """Get all search templates"""
    admin_service = AdminService(db)
    return await admin_service.get_search_templates()

@router.post("/templates", response_model=SearchTemplate)
async def create_search_template(
    template: SearchTemplate,
    admin_user: dict = Depends(get_admin_user),
# db: Session = Depends(get_db)  # Temporarily disabled
):
    """Create a new search template"""
    admin_service = AdminService(db)
    return await admin_service.create_search_template(template)

@router.get("/logs", response_model=List[SearchLog])
async def get_search_logs(
    search_id: Optional[str] = Query(None, description="Filter by search ID"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    limit: int = Query(100, ge=1, le=1000),
    admin_user: dict = Depends(get_admin_user),
# db: Session = Depends(get_db)  # Temporarily disabled
):
    """Get search logs"""
    admin_service = AdminService(db)
    return await admin_service.get_search_logs(search_id=search_id, level=level, limit=limit)

@router.get("/config", response_model=SystemConfig)
async def get_system_config(
    admin_user: dict = Depends(get_admin_user)
):
    """Get current system configuration"""
    return SystemConfig(
        max_concurrent_searches=getattr(settings, 'MAX_CONCURRENT_SEARCHES', 5),
        default_rate_limit=getattr(settings, 'RATE_LIMIT_REQUESTS', 100),
        cache_enabled=settings.ENABLE_CACHE,
        cache_expiry=settings.CACHE_EXPIRY,
        maintenance_mode=getattr(settings, 'MAINTENANCE_MODE', False)
    )

@router.post("/config")
async def update_system_config(
    config: SystemConfig,
    admin_user: dict = Depends(get_admin_user)
):
    """Update system configuration"""
    # In a real implementation, you'd persist these settings
    # For now, we'll just update the cache
    await cache.set("system_config", config.dict(), expire=86400)
    return {"message": "Configuration updated successfully"}

@router.post("/maintenance")
async def toggle_maintenance_mode(
    enabled: bool,
    admin_user: dict = Depends(get_admin_user)
):
    """Enable or disable maintenance mode"""
    await cache.set("maintenance_mode", enabled, expire=86400)
    return {"message": f"Maintenance mode {'enabled' if enabled else 'disabled'}"}

@router.get("/health")
async def admin_health_check(
    admin_user: dict = Depends(get_admin_user),
# db: Session = Depends(get_db)  # Temporarily disabled
):
    """Detailed system health check for admins"""
    admin_service = AdminService(db)
    return await admin_service.get_system_health()

@router.post("/cache/clear")
async def clear_cache(
    pattern: Optional[str] = Query(None, description="Clear specific cache pattern"),
    admin_user: dict = Depends(get_admin_user)
):
    """Clear application cache"""
    if pattern:
        # Clear specific pattern (would need Redis pattern deletion)
        count = await cache.delete_pattern(pattern)
        return {"message": f"Cleared {count} cache entries matching pattern '{pattern}'"}
    else:
        # Clear all cache
        cache.clear()
        return {"message": "All cache cleared successfully"}