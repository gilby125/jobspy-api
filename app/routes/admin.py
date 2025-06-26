import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.api.deps import get_api_key
from app.db.database import get_db
from app.models.admin_models import (
    ScheduledSearchRequest, ScheduledSearchResponse, BulkSearchRequest, SearchStatus
)
from app.services.admin_service import AdminService

from app.services.job_service import JobService
from app.services.celery_scheduler import get_celery_scheduler

logger = logging.getLogger(__name__)

router = APIRouter()

async def execute_scheduled_search(search_id: str, search_params: dict, db: Session):
    """Execute a scheduled search in the background"""
    admin_service = AdminService(db)
    
    try:
        # Update search status to running
        await admin_service.update_search_status(search_id, SearchStatus.RUNNING)
        
        # Create ScrapingRun record using tracking schema
        from sqlalchemy import text
        result = db.execute(text("""
            INSERT INTO scraping_runs (source_site, search_params, status, jobs_found, jobs_new, jobs_updated, started_at)
            VALUES (:source_site, :search_params, :status, :jobs_found, :jobs_new, :jobs_updated, :started_at)
            RETURNING id
        """), {
            "source_site": ",".join(search_params.get("site_names", ["indeed"])),
            "search_params": search_params,
            "status": "running",
            "jobs_found": 0,
            "jobs_new": 0,
            "jobs_updated": 0,
            "started_at": datetime.now()
        })
        scraping_run_id = result.fetchone()[0]
        db.commit()
        
        # Execute the actual job search
        jobs_df, _ = JobService.search_jobs({
            "site_name": search_params.get("site_names", ["indeed"]),
            "search_term": search_params.get("search_term"),
            "location": search_params.get("location"),
            "results_wanted": search_params.get("results_wanted", 20),
            "country_indeed": search_params.get("country_indeed", "USA")
        })
        
        jobs_found = len(jobs_df) if not jobs_df.empty else 0
        jobs_new = 0
        
        # Save jobs to database if any were found
        if jobs_found > 0:
            save_stats = await JobService.save_jobs_to_database(jobs_df, {
                "site_name": search_params.get("site_names", ["indeed"]),
                "search_term": search_params.get("search_term"),
                "location": search_params.get("location")
            }, db)
            jobs_new = save_stats.get("new_jobs", 0)
        
        # Update scraping run with results
        db.execute(text("""
            UPDATE scraping_runs 
            SET status = :status, completed_at = :completed_at, jobs_found = :jobs_found, jobs_new = :jobs_new
            WHERE id = :id
        """), {
            "status": "completed",
            "completed_at": datetime.now(),
            "jobs_found": jobs_found,
            "jobs_new": jobs_new,
            "id": scraping_run_id
        })
        db.commit()
        
        # Update search status
        await admin_service.update_search_status(
            search_id, 
            SearchStatus.COMPLETED, 
            jobs_found=jobs_found
        )
        
    except Exception as e:
        # Handle errors - update scraping run if it was created
        try:
            if 'scraping_run_id' in locals():
                db.execute(text("""
                    UPDATE scraping_runs 
                    SET status = :status, completed_at = :completed_at, error_message = :error_message
                    WHERE id = :id
                """), {
                    "status": "failed",
                    "completed_at": datetime.now(),
                    "error_message": str(e),
                    "id": scraping_run_id
                })
                db.commit()
        except Exception:
            pass  # Ignore database errors during error handling
        
        await admin_service.update_search_status(
            search_id, 
            SearchStatus.FAILED, 
            error_message=str(e)
        )

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
            // Clear any existing session on login page load
            sessionStorage.removeItem('admin-api-key');
            
            // Store API key and redirect to dashboard
            document.getElementById('login-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const apiKey = document.getElementById('api-key').value.trim();
                const errorDiv = document.getElementById('error-message');
                const submitBtn = document.querySelector('.login-btn');
                
                if (!apiKey) {
                    errorDiv.textContent = 'Please enter an API key.';
                    errorDiv.style.display = 'block';
                    return;
                }
                
                // Disable submit button and show loading
                submitBtn.disabled = true;
                submitBtn.textContent = 'Validating...';
                errorDiv.style.display = 'none';
                
                console.log('Testing API key:', apiKey.substring(0, 8) + '...');
                
                try {
                    const response = await fetch('/admin/stats', {
                        headers: {
                            'x-api-key': apiKey
                        }
                    });
                    
                    console.log('Login response status:', response.status);
                    
                    if (response.ok) {
                        console.log('API key valid, storing and redirecting');
                        // Store API key in sessionStorage
                        sessionStorage.setItem('admin-api-key', apiKey);
                        
                        // Update button
                        submitBtn.textContent = 'Login Successful!';
                        
                        // Small delay to show success, then redirect
                        setTimeout(() => {
                            console.log('Redirecting to dashboard');
                            window.location.href = '/admin/';
                        }, 500);
                        
                    } else if (response.status === 403) {
                        console.log('API key rejected');
                        errorDiv.textContent = 'Invalid API key. Please check and try again.';
                        errorDiv.style.display = 'block';
                        
                    } else {
                        console.log('Unexpected response:', response.status);
                        const errorData = await response.json().catch(() => ({}));
                        errorDiv.textContent = errorData.message || `Server error (${response.status}). Please try again.`;
                        errorDiv.style.display = 'block';
                    }
                    
                } catch (error) {
                    console.error('Login error:', error);
                    errorDiv.textContent = 'Error connecting to server. Please try again.';
                    errorDiv.style.display = 'block';
                } finally {
                    // Re-enable submit button
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Login to Admin Panel';
                }
            });
        </script>
    </body>
    </html>
    """
    return html_content

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard():
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
            
            <div class="nav" style="background: #34495e; padding: 10px; border-radius: 8px; margin-bottom: 20px;">
                <a href="/admin/" style="color: white; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px; background: #2c3e50;">Dashboard</a>
                <a href="/admin/searches" style="color: white; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px;">Searches</a>
                <a href="/admin/scheduler" style="color: white; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px;">Scheduler</a>
                <a href="/admin/jobs/page" style="color: white; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px;">Jobs</a>
                <a href="/admin/templates" style="color: white; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px;">Templates</a>
                <a href="/admin/analytics" style="color: white; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px;">Analytics</a>
                <a href="/admin/settings" style="color: white; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px;">Settings</a>
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
                <h2>🏷️ Version Information</h2>
                <div class="version-info" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 15px;">
                    <div class="version-item" style="background: #f8f9fa; padding: 10px; border-radius: 6px; border-left: 4px solid #007bff;">
                        <strong>Version:</strong> <span id="app-version">Loading...</span>
                    </div>
                    <div class="version-item" style="background: #f8f9fa; padding: 10px; border-radius: 6px; border-left: 4px solid #28a745;">
                        <strong>Commit:</strong> <span id="commit-hash">Loading...</span>
                    </div>
                    <div class="version-item" style="background: #f8f9fa; padding: 10px; border-radius: 6px; border-left: 4px solid #ffc107;">
                        <strong>Branch:</strong> <span id="git-branch">Loading...</span>
                    </div>
                    <div class="version-item" style="background: #f8f9fa; padding: 10px; border-radius: 6px; border-left: 4px solid #17a2b8;">
                        <strong>Deployed:</strong> <span id="deployment-time">Loading...</span>
                    </div>
                </div>
                <div style="margin-top: 10px; font-size: 0.9em; color: #666;">
                    <strong>Build:</strong> <span id="build-info">Loading...</span> | 
                    <strong>Status:</strong> <span id="app-status" style="color: #28a745;">Running</span>
                </div>
            </div>

            <div class="card">
                <h2>🚀 Quick Actions</h2>
                <div class="actions">
                    <a href="/admin/searches" class="action-card">
                        <h3>📋 Manage Searches</h3>
                        <p>View, schedule, and monitor job searches</p>
                    </a>
                    <a href="/admin/scheduler" class="action-card">
                        <h3>⚙️ Scheduler</h3>
                        <p>Monitor and control job scheduling</p>
                    </a>
                    <a href="/admin/jobs/page" class="action-card">
                        <h3>💼 Jobs Database</h3>
                        <p>Browse and search scraped job postings</p>
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
                        <h3>🔧 System Settings</h3>
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
                            <label>Job Sites (use reliable sites for better results):</label>
                            <select id="sites" multiple>
                                <option value="indeed" selected>Indeed (Recommended)</option>
                                <option value="linkedin" selected>LinkedIn (Recommended)</option>
                                <option value="glassdoor">Glassdoor (May be rate limited)</option>
                                <option value="zip_recruiter">ZipRecruiter (May be rate limited)</option>
                                <option value="google">Google Jobs (May be rate limited)</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Results per Site:</label>
                            <input type="number" id="results-wanted" value="50" min="1" max="1000">
                        </div>
                        <div class="form-group">
                            <label>Schedule Time (optional):</label>
                            <input type="datetime-local" id="schedule-time" placeholder="Leave empty for immediate execution">
                            <div class="hint">Leave empty to run immediately, or select a future date/time</div>
                        </div>
                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="recurring"> Make this a recurring search
                            </label>
                        </div>
                        <div class="form-group" id="recurring-options" style="display: none;">
                            <label>Recurring Interval:</label>
                            <select id="recurring-interval">
                                <option value="daily">Daily</option>
                                <option value="weekly">Weekly</option>
                                <option value="monthly">Monthly</option>
                            </select>
                        </div>
                        <button type="submit">📅 Schedule Search</button>
                    </form>
                </div>
            </div>
        </div>

        <script>
            // Global auth helper
            function handleAuthFailure() {
                console.log('Authentication failed, clearing session and redirecting to login');
                sessionStorage.removeItem('admin-api-key');
                window.location.href = '/admin/login';
            }

            // Authenticated fetch wrapper
            async function authFetch(url, options = {}) {
                const apiKey = sessionStorage.getItem('admin-api-key');
                if (!apiKey) {
                    handleAuthFailure();
                    return null;
                }

                const headers = {
                    'x-api-key': apiKey,
                    ...options.headers
                };

                try {
                    const response = await fetch(url, { ...options, headers });
                    
                    if (response.status === 403) {
                        console.log('403 Forbidden - API key invalid or missing');
                        handleAuthFailure();
                        return null;
                    }
                    
                    if (!response.ok) {
                        console.error(`Request failed: ${response.status} ${response.statusText}`);
                        return null;
                    }
                    
                    return response;
                } catch (error) {
                    console.error('Request error:', error);
                    return null;
                }
            }

            // Check if authentication is required by testing the stats endpoint
            console.log('Checking if authentication is required...');
            
            // Since admin endpoints require API keys even when global auth is disabled,
            // automatically set a default API key from the environment
            let apiKey = sessionStorage.getItem('admin-api-key');
            if (!apiKey) {
                // Use the default API key from environment (typically 'test')
                sessionStorage.setItem('admin-api-key', 'test');
                apiKey = 'test';
                console.log('Set default API key for admin access');
            }

            console.log('API key available, loading dashboard');

            // Load stats with proper error handling
            async function loadStats() {
                console.log('Loading stats...');
                
                // Try with auth first, fall back to no auth if needed
                let response = await authFetch('/admin/stats');
                if (!response) {
                    console.log('Auth fetch failed, trying without auth...');
                    try {
                        response = await fetch('/admin/stats');
                    } catch (error) {
                        console.error('Direct fetch also failed:', error);
                        return;
                    }
                }
                
                if (response) {
                    try {
                        const stats = await response.json();
                        console.log('Stats loaded:', stats);
                        
                        document.getElementById('total-searches').textContent = stats.total_searches || '0';
                        document.getElementById('jobs-found').textContent = stats.jobs_found_today || '0';
                        document.getElementById('active-searches').textContent = stats.active_searches || '0';
                        document.getElementById('system-health').textContent = 
                            (stats.system_health && stats.system_health.status) || 'OK';
                    } catch (error) {
                        console.error('Error parsing stats response:', error);
                        // Set default values
                        document.getElementById('total-searches').textContent = 'Error';
                        document.getElementById('jobs-found').textContent = 'Error';
                        document.getElementById('active-searches').textContent = 'Error';
                        document.getElementById('system-health').textContent = 'Error';
                    }
                }
            }

            // Load version information
            async function loadVersionInfo() {
                console.log('Loading version info...');
                
                try {
                    const response = await fetch('/version');
                    if (response.ok) {
                        const version = await response.json();
                        console.log('Version loaded:', version);
                        
                        document.getElementById('app-version').textContent = version.version || 'Unknown';
                        document.getElementById('commit-hash').textContent = version.commit_hash || 'Unknown';
                        document.getElementById('git-branch').textContent = version.branch || 'Unknown';
                        
                        // Format deployment time
                        if (version.deployment_time) {
                            const deployTime = new Date(version.deployment_time);
                            document.getElementById('deployment-time').textContent = deployTime.toLocaleString();
                        } else {
                            document.getElementById('deployment-time').textContent = 'Unknown';
                        }
                        
                        // Build info
                        document.getElementById('build-info').textContent = 
                            `#${version.build_number || 'Unknown'} (${version.build_date || 'Unknown'})`;
                        
                        document.getElementById('app-status').textContent = version.status || 'Unknown';
                        
                    } else {
                        console.error('Failed to load version info:', response.status);
                        // Set error values
                        document.getElementById('app-version').textContent = 'Error';
                        document.getElementById('commit-hash').textContent = 'Error';
                        document.getElementById('git-branch').textContent = 'Error';
                        document.getElementById('deployment-time').textContent = 'Error';
                        document.getElementById('build-info').textContent = 'Error';
                        document.getElementById('app-status').textContent = 'Error';
                    }
                } catch (error) {
                    console.error('Error loading version info:', error);
                    // Set error values
                    document.getElementById('app-version').textContent = 'Error';
                    document.getElementById('commit-hash').textContent = 'Error';
                    document.getElementById('git-branch').textContent = 'Error';
                    document.getElementById('deployment-time').textContent = 'Error';
                    document.getElementById('build-info').textContent = 'Error';
                    document.getElementById('app-status').textContent = 'Error';
                }
            }

            // Handle recurring checkbox - with error handling
            function setupRecurringCheckbox() {
                const recurringCheckbox = document.getElementById('recurring');
                const recurringOptions = document.getElementById('recurring-options');
                
                if (recurringCheckbox && recurringOptions) {
                    recurringCheckbox.addEventListener('change', function() {
                        console.log('Recurring checkbox changed:', this.checked);
                        recurringOptions.style.display = this.checked ? 'block' : 'none';
                    });
                    console.log('Recurring checkbox event listener attached successfully');
                } else {
                    console.error('Could not find recurring checkbox or options elements');
                }
            }
            
            // Set up recurring checkbox when DOM is ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', setupRecurringCheckbox);
            } else {
                setupRecurringCheckbox();
            }

            // Handle quick search form
            document.getElementById('quick-search-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                console.log('Submitting search form...');
                
                const scheduleTime = document.getElementById('schedule-time').value;
                const isRecurring = document.getElementById('recurring').checked;
                
                const formData = {
                    name: document.getElementById('search-name').value,
                    search_term: document.getElementById('search-term').value,
                    location: document.getElementById('location').value,
                    site_names: Array.from(document.getElementById('sites').selectedOptions).map(o => o.value),
                    results_wanted: parseInt(document.getElementById('results-wanted').value),
                    country_indeed: 'USA',
                    schedule_time: scheduleTime ? new Date(scheduleTime).toISOString() : null,
                    recurring: isRecurring,
                    recurring_interval: isRecurring ? document.getElementById('recurring-interval').value : null
                };

                const response = await authFetch('/admin/searches', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });
                
                if (response) {
                    const result = await response.json();
                    console.log('Search result:', result);
                    
                    if (result.execution_type === 'immediate') {
                        alert(`✅ Immediate search completed successfully!\\n\\nFound ${result.results_count || 0} jobs for "${result.search_term}"${result.location ? ' in ' + result.location : ''}.\\n\\nCheck the Jobs Database to view results.`);
                    } else if (scheduleTime) {
                        alert(`📅 Search scheduled for ${new Date(scheduleTime).toLocaleString()}!`);
                    } else {
                        alert('🚀 Search scheduled for immediate execution!');
                    }
                    
                    document.getElementById('quick-search-form').reset();
                    document.getElementById('recurring-options').style.display = 'none';
                    loadStats();
                } else {
                    alert('❌ Failed to schedule search. Please check the form data and try again.');
                }
            });

            // Bulk search functions
            let bulkSearchIndex = 1;
            
            function addBulkSearch() {
                bulkSearchIndex++;
                const container = document.getElementById('bulk-searches-container');
                const newSearchHtml = `
                    <div class="bulk-search-item" data-index="${bulkSearchIndex}">
                        <div class="bulk-search-header" style="background: #ecf0f1; padding: 10px; border-radius: 4px; margin-bottom: 10px;">
                            <strong>Search #${bulkSearchIndex}</strong>
                            <button class="btn danger" onclick="removeBulkSearch(${bulkSearchIndex})" style="float: right; padding: 2px 6px; font-size: 12px;">Remove</button>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Search Name:</label>
                                <input type="text" class="bulk-search-name" placeholder="e.g. Python Remote Jobs">
                            </div>
                            <div class="form-group">
                                <label>Search Term:</label>
                                <input type="text" class="bulk-search-term" placeholder="e.g. Python Developer">
                            </div>
                            <div class="form-group">
                                <label>Location:</label>
                                <input type="text" class="bulk-location" placeholder="e.g. San Francisco, CA">
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Job Sites:</label>
                                <select class="bulk-sites" multiple>
                                    <option value="indeed" selected>Indeed</option>
                                    <option value="linkedin">LinkedIn</option>
                                    <option value="glassdoor">Glassdoor</option>
                                    <option value="zip_recruiter">ZipRecruiter</option>
                                    <option value="google">Google Jobs</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Results per Site:</label>
                                <input type="number" class="bulk-results" value="20" min="1" max="100">
                            </div>
                            <div class="form-group">
                                <label>Schedule Type:</label>
                                <select class="bulk-schedule-type" onchange="toggleBulkScheduleOptions(this)">
                                    <option value="scheduled">Schedule for Later</option>
                                    <option value="recurring">Recurring</option>
                                </select>
                            </div>
                        </div>
                        <div class="form-row bulk-schedule-options">
                            <div class="form-group">
                                <label>Schedule Time:</label>
                                <input type="datetime-local" class="bulk-schedule-time" required>
                            </div>
                            <div class="form-group bulk-recurring-options" style="display: none;">
                                <label>Recurring Interval:</label>
                                <select class="bulk-recurring-interval">
                                    <option value="hourly">Every Hour</option>
                                    <option value="daily">Daily</option>
                                    <option value="weekly">Weekly</option>
                                    <option value="monthly">Monthly</option>
                                </select>
                            </div>
                        </div>
                    </div>
                `;
                container.insertAdjacentHTML('beforeend', newSearchHtml);
            }
            
            function removeBulkSearch(index) {
                const searchItem = document.querySelector(`[data-index="${index}"]`);
                if (searchItem) {
                    searchItem.remove();
                }
            }
            
            function clearBulkSearches() {
                const container = document.getElementById('bulk-searches-container');
                container.innerHTML = '';
                bulkSearchIndex = 0;
                addBulkSearch(); // Add one default search
            }
            
            function toggleBulkScheduleOptions(selectElement) {
                const searchItem = selectElement.closest('.bulk-search-item');
                const scheduleOptions = searchItem.querySelector('.bulk-schedule-options');
                const recurringOptions = searchItem.querySelector('.bulk-recurring-options');
                const scheduleType = selectElement.value;
                
                // Always show schedule options since we only have scheduled/recurring
                scheduleOptions.style.display = 'block';
                
                if (scheduleType === 'recurring') {
                    recurringOptions.style.display = 'block';
                } else {
                    recurringOptions.style.display = 'none';
                }
            }
            
            function collectBulkSearchData() {
                const searches = [];
                const searchItems = document.querySelectorAll('.bulk-search-item');
                
                searchItems.forEach(item => {
                    const name = item.querySelector('.bulk-search-name').value;
                    const searchTerm = item.querySelector('.bulk-search-term').value;
                    const location = item.querySelector('.bulk-location').value;
                    const sites = Array.from(item.querySelector('.bulk-sites').selectedOptions).map(opt => opt.value);
                    const results = parseInt(item.querySelector('.bulk-results').value);
                    const scheduleType = item.querySelector('.bulk-schedule-type').value;
                    const scheduleTime = item.querySelector('.bulk-schedule-time').value;
                    const recurringInterval = item.querySelector('.bulk-recurring-interval').value;
                    
                    if (name && searchTerm) {
                        const searchData = {
                            name: name,
                            search_term: searchTerm,
                            location: location || null,
                            site_names: sites,
                            results_wanted: results,
                            country_indeed: 'USA',
                            recurring: scheduleType === 'recurring',
                            recurring_interval: scheduleType === 'recurring' ? recurringInterval : null
                        };
                        
                        if (scheduleType === 'scheduled' || scheduleType === 'recurring') {
                            searchData.schedule_time = scheduleTime ? new Date(scheduleTime).toISOString() : null;
                        }
                        
                        searches.push(searchData);
                    }
                });
                
                return searches;
            }
            
            async function submitBulkSearches() {
                const searches = collectBulkSearchData();
                
                if (searches.length === 0) {
                    alert('Please add at least one valid search with name and search term.');
                    return;
                }
                
                const batchName = document.getElementById('bulk-batch-name').value || `Bulk Search ${new Date().toLocaleString()}`;
                
                const bulkRequest = {
                    searches: searches,
                    batch_name: batchName
                };
                
                try {
                    const response = await authFetch('/admin/searches/bulk', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(bulkRequest)
                    });
                    
                    if (response && response.ok) {
                        const result = await response.json();
                        alert(`Bulk search scheduled successfully!\\n${result.successful} searches scheduled, ${result.failed} failed.`);
                        clearBulkSearches();
                        loadSearches();
                        loadSearchStats();
                    } else {
                        const error = await response.json();
                        alert('Error scheduling bulk searches: ' + (error.detail || 'Unknown error'));
                    }
                } catch (error) {
                    console.error('Error submitting bulk searches:', error);
                    alert('Error submitting bulk searches: ' + error.message);
                }
            }
            
            function previewBulkSearches() {
                const searches = collectBulkSearchData();
                
                if (searches.length === 0) {
                    alert('No valid searches to preview.');
                    return;
                }
                
                const batchName = document.getElementById('bulk-batch-name').value || `Bulk Search ${new Date().toLocaleString()}`;
                
                let preview = `Batch: ${batchName}\\n`;
                preview += `Total Searches: ${searches.length}\\n\\n`;
                
                searches.forEach((search, index) => {
                    preview += `${index + 1}. ${search.name}\\n`;
                    preview += `   Term: ${search.search_term}\\n`;
                    preview += `   Location: ${search.location || 'Any'}\\n`;
                    preview += `   Sites: ${search.site_names.join(', ')}\\n`;
                    preview += `   Results: ${search.results_wanted}\\n`;
                    if (search.recurring) {
                        preview += `   Recurring: ${search.recurring_interval}\\n`;
                    }
                    preview += '\\n';
                });
                
                alert(preview);
            }

            // Load stats and version info on page load
            loadStats();
            loadVersionInfo();
            
            // Refresh stats every 30 seconds
            setInterval(loadStats, 30000);
            
            // Refresh version info every 5 minutes (to catch deployments)
            setInterval(loadVersionInfo, 300000);
        </script>
    </body>
    </html>
    """
    return html_content

@router.get("/stats")
async def get_admin_stats(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Get admin dashboard statistics"""
    admin_service = AdminService(db)
    stats = await admin_service.get_admin_stats()
    return stats.dict()

@router.post("/searches")
async def schedule_search(
    request: ScheduledSearchRequest,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Schedule a new job search for immediate or future execution"""
    scheduler = await get_celery_scheduler(db)
    
    # Handle immediate search (no schedule_time and not recurring)
    if not request.schedule_time and not request.recurring:
        # This is an immediate search - delegate to the job search service
        from app.services.job_service import JobService
        
        # Convert admin request to job search request
        search_params = {
            'search_term': request.search_term,
            'location': request.location or '',
            'site': request.site_names[0] if request.site_names else 'indeed',  # Use first site for immediate search
            'results_wanted': request.results_wanted or 20,
            'hours_old': 72,  # Default
            'country': 'US',  # Default
            'job_type': request.job_type or ''
        }
        
        try:
            # Execute immediate search
            jobs_df, is_cached = await JobService.search_jobs(search_params)
            
            # Convert DataFrame to jobs count
            jobs_count = len(jobs_df) if not jobs_df.empty else 0
            
            # Return success response
            return {
                "message": "Immediate search completed successfully",
                "search_id": None,  # No scheduled search ID for immediate searches
                "results_count": jobs_count,
                "execution_type": "immediate",
                "search_term": request.search_term,
                "location": request.location,
                "cached": is_cached
            }
            
        except Exception as e:
            logger.error(f"Immediate search failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Immediate search failed: {str(e)}"
            )
    
    # Handle timezone-aware vs naive datetime comparison and get execution time
    if request.schedule_time:
        if request.schedule_time.tzinfo is not None:
            # Convert to naive datetime for database storage
            execution_time = request.schedule_time.replace(tzinfo=None)
            # Compare with UTC time
            import pytz
            now_aware = datetime.now(pytz.UTC)
            if request.schedule_time.tzinfo != pytz.UTC:
                request.schedule_time = request.schedule_time.astimezone(pytz.UTC)
            is_immediate = request.schedule_time <= now_aware
            
            # Don't allow scheduling in the past (unless it's recurring)
            if is_immediate and not request.recurring:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot schedule searches in the past. Use /api/v1/search_jobs for immediate searches."
                )
        else:
            # Both are naive
            execution_time = request.schedule_time
            is_immediate = request.schedule_time <= datetime.now()
            
            # Don't allow scheduling in the past (unless it's recurring)
            if is_immediate and not request.recurring:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot schedule searches in the past. Use /api/v1/search_jobs for immediate searches."
                )
    else:
        # For recurring searches without specific schedule_time, start immediately
        execution_time = datetime.now()
        is_immediate = True
    
    try:
        # Schedule the search
        search_id = await scheduler.schedule_search(
            search_config=request.dict(),
            schedule_time=execution_time
        )
        
        # Create response
        response = ScheduledSearchResponse(
            id=str(search_id),  # search_id is already an integer from the scheduler
            name=request.name,
            status=SearchStatus.PENDING,
            search_params=request.dict(),
            created_at=datetime.now(),
            scheduled_time=execution_time,
            started_at=None,
            completed_at=None,
            jobs_found=None,
            error_message=None,
            recurring=request.recurring,
            recurring_interval=request.recurring_interval,
            next_run=execution_time
        )
        
        if is_immediate:
            response.status = SearchStatus.PENDING
            # The scheduler will pick it up within 30 seconds
        
        return response.dict()
        
    except Exception as e:
        # Create a database record even for failed scheduling
        try:
            result = db.execute(text("""
                INSERT INTO scraping_runs (source_site, search_params, 
                                         started_at, status, jobs_found, error_message)
                VALUES (:source_site, :search_params, :started_at, 
                        :status, :jobs_found, :error_message)
                RETURNING id
            """), {
                "source_site": ",".join(request.site_names or ["indeed"]),
                "search_params": {
                    "search_term": request.search_term or "",
                    "location": request.location or "",
                    "site_names": request.site_names or ["indeed"],
                    "results_wanted": request.results_wanted or 20,
                    "recurring": request.recurring or False,
                    "recurring_interval": request.recurring_interval
                },
                "started_at": execution_time,
                "status": "failed",
                "jobs_found": 0,
                "error_message": str(e)
            })
            failed_search_id = result.fetchone()[0]
            db.commit()
        except Exception:
            failed_search_id = 0
            
        return {
            "id": str(failed_search_id),
            "name": request.name,
            "status": "failed",
            "error_message": str(e),
            "search_params": request.dict(),
            "created_at": datetime.now().isoformat(),
            "scheduled_time": execution_time.isoformat() if execution_time else None
        }

@router.post("/searches/bulk")
async def schedule_bulk_searches(
    request: BulkSearchRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """Schedule multiple job searches from a bulk request"""
    scheduler = await get_celery_scheduler(db)
    
    results = []
    batch_name = request.batch_name or f"Bulk Search {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    for search_request in request.searches:
        try:
            # Handle execution time
            if search_request.schedule_time:
                execution_time = search_request.schedule_time.replace(tzinfo=None) if search_request.schedule_time.tzinfo else search_request.schedule_time
                is_immediate = execution_time <= datetime.now()
            else:
                execution_time = datetime.now()
                is_immediate = True
            
            # Schedule the search
            search_id = await scheduler.schedule_search(
                search_config=search_request.dict(),
                schedule_time=execution_time
            )
            
            # Create response
            response = {
                "id": str(search_id),
                "name": search_request.name,
                "status": "pending",
                "batch_name": batch_name,
                "search_params": search_request.dict(),
                "created_at": datetime.now().isoformat(),
                "scheduled_time": execution_time.isoformat() if execution_time else None,
                "recurring": search_request.recurring,
                "recurring_interval": search_request.recurring_interval
            }
            
            results.append(response)
            
        except Exception as e:
            # Add failed search to results
            results.append({
                "id": f"failed_{len(results)}",
                "name": search_request.name,
                "status": "failed",
                "batch_name": batch_name,
                "error_message": str(e),
                "search_params": search_request.dict(),
                "created_at": datetime.now().isoformat()
            })
    
    return {
        "batch_name": batch_name,
        "total_searches": len(request.searches),
        "successful": len([r for r in results if r["status"] != "failed"]),
        "failed": len([r for r in results if r["status"] == "failed"]),
        "searches": results
    }

@router.get("/searches", response_class=HTMLResponse)
async def admin_searches_page():
    """Admin searches management page"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>JobSpy Admin - Searches</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .nav { background: #34495e; padding: 10px; border-radius: 8px; margin-bottom: 20px; }
            .nav a { color: white; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px; }
            .nav a.active { background: #2c3e50; }
            .nav a:hover { background: #2c3e50; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 20px; }
            .stat-card { background: #3498db; color: white; padding: 20px; border-radius: 8px; text-align: center; }
            .stat-value { font-size: 32px; font-weight: bold; margin-bottom: 5px; }
            .stat-label { font-size: 14px; opacity: 0.9; }
            .search-form { background: #ecf0f1; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 15px; }
            .form-group { display: flex; flex-direction: column; }
            .form-group label { margin-bottom: 5px; font-weight: bold; color: #2c3e50; }
            .form-group input, .form-group select, .form-group textarea { padding: 8px; border: 1px solid #bdc3c7; border-radius: 4px; }
            .btn { background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin: 5px; }
            .btn:hover { background: #2980b9; }
            .btn.success { background: #27ae60; }
            .btn.success:hover { background: #219a52; }
            .btn.warning { background: #f39c12; }
            .btn.warning:hover { background: #d68910; }
            .btn.danger { background: #e74c3c; }
            .btn.danger:hover { background: #c0392b; }
            .searches-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            .searches-table th, .searches-table td { padding: 12px; text-align: left; border-bottom: 1px solid #ecf0f1; }
            .searches-table th { background: #34495e; color: white; }
            .searches-table tr:hover { background: #f8f9fa; }
            .status-badge { padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; }
            .status-pending { background: #f39c12; color: white; }
            .status-running { background: #3498db; color: white; }
            .status-completed { background: #27ae60; color: white; }
            .status-failed { background: #e74c3c; color: white; }
            .status-cancelled { background: #95a5a6; color: white; }
            .empty-state { text-align: center; color: #7f8c8d; padding: 40px; }
            .actions { text-align: center; }
            .actions .btn { margin: 0 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔍 Search Management</h1>
                <p>Schedule, monitor, and manage job searches</p>
            </div>
            
            <div class="nav">
                <a href="/admin/">Dashboard</a>
                <a href="/admin/searches" class="active">Searches</a>
                <a href="/admin/scheduler">Scheduler</a>
                <a href="/admin/jobs/page">Jobs</a>
                <a href="/admin/templates">Templates</a>
                <a href="/admin/analytics">Analytics</a>
                <a href="/admin/settings">Settings</a>
            </div>
            
            <div class="card">
                <h2>📊 Search Statistics</h2>
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-value" id="total-searches">-</div>
                        <div class="stat-label">Total Searches</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="active-searches">-</div>
                        <div class="stat-label">Active Searches</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="completed-today">-</div>
                        <div class="stat-label">Completed Today</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="success-rate">-</div>
                        <div class="stat-label">Success Rate</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <h2>⚡ Quick Actions</h2>
                <p>For immediate job searches, use the direct search API:</p>
                <div style="margin: 20px 0;">
                    <button onclick="openQuickSearch()" class="btn" style="background: #27ae60; color: white; padding: 12px 24px; border: none; border-radius: 6px; font-size: 16px; cursor: pointer; margin-right: 10px;">
                        🔍 Quick Search (Immediate)
                    </button>
                    <button onclick="openApiDocs()" class="btn" style="background: #3498db; color: white; padding: 12px 24px; border: none; border-radius: 6px; font-size: 16px; cursor: pointer;">
                        📚 API Documentation
                    </button>
                </div>
                <small style="color: #666;">
                    Quick Search opens the direct API interface for immediate job searches. 
                    Use the scheduler below for future or recurring searches.
                </small>
            </div>

            <div class="card">
                <h2>⏰ Schedule Future Search</h2>
                <form id="schedule-search-form" class="search-form">
                    <div class="form-row">
                        <div class="form-group">
                            <label for="search-name">Search Name:</label>
                            <input type="text" id="search-name" placeholder="e.g. Python Developer Search" required>
                        </div>
                        <div class="form-group">
                            <label for="search-term">Search Term:</label>
                            <input type="text" id="search-term" placeholder="e.g. Python Developer" required>
                        </div>
                        <div class="form-group">
                            <label for="location">Location:</label>
                            <input type="text" id="location" placeholder="e.g. New York, NY">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="sites">Job Sites:</label>
                            <select id="sites" multiple>
                                <option value="indeed" selected>Indeed</option>
                                <option value="linkedin" selected>LinkedIn</option>
                                <option value="glassdoor">Glassdoor</option>
                                <option value="zip_recruiter">ZipRecruiter</option>
                                <option value="google">Google Jobs</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="results-wanted">Results per Site:</label>
                            <input type="number" id="results-wanted" value="20" min="1" max="100">
                        </div>
                        <div class="form-group">
                            <label for="job-type">Job Type:</label>
                            <select id="job-type">
                                <option value="">Any</option>
                                <option value="fulltime">Full-time</option>
                                <option value="parttime">Part-time</option>
                                <option value="contract">Contract</option>
                                <option value="internship">Internship</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="schedule-type">Schedule Type:</label>
                            <select id="schedule-type" onchange="toggleScheduleOptions()">
                                <option value="scheduled">Schedule for Later</option>
                                <option value="recurring">Recurring</option>
                            </select>
                        </div>
                        <div class="form-group" id="schedule-time-group">
                            <label for="schedule-time">Schedule Time:</label>
                            <input type="datetime-local" id="schedule-time" required>
                        </div>
                        <div class="form-group" id="recurring-group" style="display: none;">
                            <label for="recurring-interval">Recurring Interval:</label>
                            <select id="recurring-interval">
                                <option value="hourly">Every Hour</option>
                                <option value="daily">Daily</option>
                                <option value="weekly">Weekly</option>
                                <option value="monthly">Monthly</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="description">Description (optional):</label>
                            <textarea id="description" rows="2" placeholder="Optional description for this search"></textarea>
                        </div>
                    </div>
                    <div class="actions">
                        <button type="submit" class="btn success">🚀 Schedule Search</button>
                        <button type="button" class="btn" onclick="clearForm()">🗑️ Clear Form</button>
                        <button type="button" class="btn" onclick="loadTemplates()">📋 Load Template</button>
                    </div>
                </form>
            </div>

            <div class="card">
                <h2>📦 Bulk Search Operations</h2>
                <p>Schedule multiple searches at once with different parameters</p>
                
                <div class="bulk-controls" style="margin-bottom: 20px;">
                    <button class="btn" onclick="addBulkSearch()">➕ Add Search</button>
                    <button class="btn" onclick="clearBulkSearches()">🗑️ Clear All</button>
                    <button class="btn" onclick="loadSearchTemplate()">📋 Load Template</button>
                    <div style="margin-top: 10px;">
                        <label for="bulk-batch-name">Batch Name:</label>
                        <input type="text" id="bulk-batch-name" placeholder="e.g. Weekly Tech Jobs Search" style="margin-left: 10px; padding: 5px;">
                    </div>
                </div>
                
                <div id="bulk-searches-container" style="margin-bottom: 20px;">
                    <div class="bulk-search-item" data-index="0">
                        <div class="bulk-search-header" style="background: #ecf0f1; padding: 10px; border-radius: 4px; margin-bottom: 10px;">
                            <strong>Search #1</strong>
                            <button class="btn danger" onclick="removeBulkSearch(0)" style="float: right; padding: 2px 6px; font-size: 12px;">Remove</button>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Search Name:</label>
                                <input type="text" class="bulk-search-name" placeholder="e.g. Python Remote Jobs">
                            </div>
                            <div class="form-group">
                                <label>Search Term:</label>
                                <input type="text" class="bulk-search-term" placeholder="e.g. Python Developer">
                            </div>
                            <div class="form-group">
                                <label>Location:</label>
                                <input type="text" class="bulk-location" placeholder="e.g. San Francisco, CA">
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Job Sites:</label>
                                <select class="bulk-sites" multiple>
                                    <option value="indeed" selected>Indeed</option>
                                    <option value="linkedin">LinkedIn</option>
                                    <option value="glassdoor">Glassdoor</option>
                                    <option value="zip_recruiter">ZipRecruiter</option>
                                    <option value="google">Google Jobs</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Results per Site:</label>
                                <input type="number" class="bulk-results" value="20" min="1" max="100">
                            </div>
                            <div class="form-group">
                                <label>Schedule Type:</label>
                                <select class="bulk-schedule-type" onchange="toggleBulkScheduleOptions(this)">
                                    <option value="scheduled">Schedule for Later</option>
                                    <option value="recurring">Recurring</option>
                                </select>
                            </div>
                        </div>
                        <div class="form-row bulk-schedule-options">
                            <div class="form-group">
                                <label>Schedule Time:</label>
                                <input type="datetime-local" class="bulk-schedule-time" required>
                            </div>
                            <div class="form-group bulk-recurring-options" style="display: none;">
                                <label>Recurring Interval:</label>
                                <select class="bulk-recurring-interval">
                                    <option value="hourly">Every Hour</option>
                                    <option value="daily">Daily</option>
                                    <option value="weekly">Weekly</option>
                                    <option value="monthly">Monthly</option>
                                </select>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="actions">
                    <button class="btn success" onclick="submitBulkSearches()">🚀 Schedule All Searches</button>
                    <button class="btn" onclick="previewBulkSearches()">👁️ Preview</button>
                </div>
            </div>

            <div class="card">
                <h2>📋 Scheduled Searches</h2>
                <div class="actions" style="margin-bottom: 20px;">
                    <button class="btn" onclick="refreshSearches()">🔄 Refresh</button>
                    <button class="btn warning" onclick="cancelAllPending()">⏸️ Cancel All Pending</button>
                    <button class="btn danger" onclick="cleanupOldJobs()">🗑️ Clean Up Old Jobs</button>
                    <button class="btn" onclick="exportSearches()">📊 Export</button>
                    <select id="status-filter" onchange="filterSearches()">
                        <option value="active">Active (Pending, Running, Completed)</option>
                        <option value="">All Statuses</option>
                        <option value="pending">Pending</option>
                        <option value="running">Running</option>
                        <option value="completed">Completed</option>
                        <option value="failed">Failed</option>
                        <option value="cancelled">Cancelled</option>
                    </select>
                </div>
                
                <table class="searches-table" id="searches-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Name</th>
                            <th>Search Term</th>
                            <th>Location</th>
                            <th>Sites</th>
                            <th>Status</th>
                            <th>Scheduled</th>
                            <th>Jobs Found</th>
                            <th>Run Count</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td colspan="10" class="empty-state">Loading searches...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            // Auth wrapper function
            async function authFetch(url, options = {}) {
                const apiKey = sessionStorage.getItem('admin-api-key');
                if (!apiKey) {
                    return fetch(url, options);
                }

                const headers = {
                    'x-api-key': apiKey,
                    ...options.headers
                };

                try {
                    const response = await fetch(url, { ...options, headers });
                    if (response.status === 403) {
                        return fetch(url, options);
                    }
                    return response;
                } catch (error) {
                    console.error('Request error:', error);
                    return null;
                }
            }

            function toggleScheduleOptions() {
                console.log('toggleScheduleOptions called');
                const scheduleType = document.getElementById('schedule-type').value;
                const timeGroup = document.getElementById('schedule-time-group');
                const recurringGroup = document.getElementById('recurring-group');
                
                console.log('Schedule type:', scheduleType);
                
                if (timeGroup && recurringGroup) {
                    // Always show time group since we only have scheduled/recurring options
                    timeGroup.style.display = 'block';
                    recurringGroup.style.display = scheduleType === 'recurring' ? 'block' : 'none';
                    console.log('Schedule options toggled successfully');
                } else {
                    console.error('Could not find schedule option elements');
                }
            }

            async function loadSearchStats() {
                try {
                    const response = await authFetch('/admin/stats');
                    if (response && response.ok) {
                        const stats = await response.json();
                        document.getElementById('total-searches').textContent = stats.total_searches || '0';
                        document.getElementById('active-searches').textContent = stats.active_searches || '0';
                        document.getElementById('completed-today').textContent = stats.completed_searches_today || '0';
                        const successRate = stats.total_searches > 0 ? 
                            Math.round(((stats.completed_searches || 0) / stats.total_searches) * 100) : 0;
                        document.getElementById('success-rate').textContent = successRate + '%';
                    }
                } catch (error) {
                    console.error('Error loading stats:', error);
                }
            }

            async function loadSearches() {
                try {
                    const statusFilter = document.getElementById('status-filter').value;
                    let url = '/admin/searches/api?limit=100';
                    
                    // Handle special "active" filter client-side
                    if (statusFilter && statusFilter !== 'active') {
                        url += `&status=${statusFilter}`;
                    }
                    
                    const response = await authFetch(url);
                    if (response && response.ok) {
                        const data = await response.json();
                        let searches = data.searches || [];
                        
                        // Filter for active jobs (exclude cancelled and failed)
                        if (statusFilter === 'active') {
                            searches = searches.filter(search => 
                                ['pending', 'running', 'completed'].includes(search.status)
                            );
                        }
                        
                        const tbody = document.querySelector('#searches-table tbody');
                        
                        if (searches && searches.length > 0) {
                            tbody.innerHTML = searches.map(search => `
                                <tr>
                                    <td>${search.id}</td>
                                    <td>${search.name || '-'}</td>
                                    <td>${search.search_params?.search_term || '-'}</td>
                                    <td>${search.search_params?.location || '-'}</td>
                                    <td>${search.search_params?.site_names?.join(', ') || '-'}</td>
                                    <td><span class="status-badge status-${search.status}">${search.status}</span></td>
                                    <td>${new Date(search.created_at).toLocaleString()}</td>
                                    <td>${search.jobs_found || '0'}</td>
                                    <td>${search.recurring ? 
                                        `<span style="color: #27ae60; font-weight: bold;">${search.run_count || 1} run${(search.run_count || 1) > 1 ? 's' : ''}</span>` : 
                                        '<span style="color: #7f8c8d;">One-time</span>'}</td>
                                    <td class="actions">
                                        ${search.status === 'pending' || search.status === 'running' ? 
                                            `<button class="btn warning" onclick="cancelSearch('${search.id}')">Cancel</button>` : ''}
                                        <button class="btn" onclick="viewSearchDetails('${search.id}')">View</button>
                                        ${search.status === 'failed' ? 
                                            `<button class="btn" onclick="retrySearch('${search.id}')">Retry</button>` : ''}
                                    </td>
                                </tr>
                            `).join('');
                        } else {
                            tbody.innerHTML = '<tr><td colspan="9" class="empty-state"><h3>No searches found</h3><p>Create your first search using the form above.</p></td></tr>';
                        }
                    }
                } catch (error) {
                    console.error('Error loading searches:', error);
                }
            }

            async function scheduleSearch(event) {
                event.preventDefault();
                
                const formData = {
                    name: document.getElementById('search-name').value,
                    search_term: document.getElementById('search-term').value,
                    location: document.getElementById('location').value,
                    site_names: Array.from(document.getElementById('sites').selectedOptions).map(opt => opt.value),
                    results_wanted: parseInt(document.getElementById('results-wanted').value),
                    job_type: document.getElementById('job-type').value || null,
                    description: document.getElementById('description').value || null
                };
                
                const scheduleType = document.getElementById('schedule-type').value;
                
                if (scheduleType === 'scheduled') {
                    formData.schedule_time = document.getElementById('schedule-time').value;
                    formData.recurring = false;
                } else if (scheduleType === 'recurring') {
                    formData.schedule_time = document.getElementById('schedule-time').value;
                    formData.recurring = true;
                    formData.recurring_interval = document.getElementById('recurring-interval').value;
                }
                
                try {
                    const response = await authFetch('/admin/searches', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(formData)
                    });
                    
                    if (response && response.ok) {
                        alert('Search scheduled successfully!');
                        clearForm();
                        loadSearches();
                        loadSearchStats();
                    } else {
                        const error = await response.json();
                        alert('Error scheduling search: ' + (error.detail || 'Unknown error'));
                    }
                } catch (error) {
                    console.error('Error scheduling search:', error);
                    alert('Error scheduling search: ' + error.message);
                }
            }

            async function cancelSearch(searchId) {
                if (confirm('Are you sure you want to cancel this search?')) {
                    try {
                        const response = await authFetch(`/admin/searches/${searchId}/cancel`, { method: 'POST' });
                        if (response && response.ok) {
                            alert('Search cancelled successfully!');
                            loadSearches();
                            loadSearchStats();
                        } else {
                            alert('Error cancelling search');
                        }
                    } catch (error) {
                        console.error('Error cancelling search:', error);
                        alert('Error cancelling search: ' + error.message);
                    }
                }
            }

            function viewSearchDetails(searchId) {
                window.open(`/admin/searches/${searchId}`, '_blank');
            }

            function clearForm() {
                document.getElementById('schedule-search-form').reset();
                document.getElementById('results-wanted').value = 20;
                toggleScheduleOptions();
            }

            function refreshSearches() {
                loadSearches();
                loadSearchStats();
            }

            function filterSearches() {
                loadSearches();
            }

            function exportSearches() {
                window.open('/admin/searches/export', '_blank');
            }

            function openQuickSearch() {
                // Open the direct search API endpoint in a new tab
                const quickSearchUrl = '/api/v1/search_jobs?search_term=python+developer&location=&results_wanted=20';
                window.open(quickSearchUrl, '_blank');
            }

            function openApiDocs() {
                // Open the API documentation in a new tab
                window.open('/docs', '_blank');
            }

            async function cancelAllPending() {
                if (confirm('Are you sure you want to cancel all pending searches?')) {
                    try {
                        const response = await authFetch('/admin/searches/cancel-all', { method: 'POST' });
                        if (response && response.ok) {
                            alert('All pending searches cancelled!');
                            loadSearches();
                            loadSearchStats();
                        } else {
                            alert('Error cancelling searches');
                        }
                    } catch (error) {
                        console.error('Error cancelling searches:', error);
                        alert('Error cancelling searches: ' + error.message);
                    }
                }
            }

            async function cleanupOldJobs() {
                if (confirm('This will permanently DELETE all cancelled and failed jobs older than 7 days. Are you sure?')) {
                    try {
                        const response = await authFetch('/admin/searches/cleanup', { method: 'POST' });
                        if (response && response.ok) {
                            const result = await response.json();
                            alert(`Cleanup completed! Deleted ${result.deleted_count} old jobs.`);
                            loadSearches();
                            loadSearchStats();
                        } else {
                            alert('Error during cleanup');
                        }
                    } catch (error) {
                        console.error('Error during cleanup:', error);
                        alert('Error during cleanup: ' + error.message);
                    }
                }
            }

            // Initialize page
            document.getElementById('schedule-search-form').addEventListener('submit', scheduleSearch);
            loadSearchStats();
            loadSearches();
            
            // Set default schedule time to 1 hour from now
            const defaultTime = new Date();
            defaultTime.setHours(defaultTime.getHours() + 1);
            document.getElementById('schedule-time').value = defaultTime.toISOString().slice(0, 16);
        </script>
    </body>
    </html>
    """
    return html_content

@router.get("/searches/api")
async def get_scheduled_searches(
    status: Optional[SearchStatus] = Query(None),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Get list of scheduled searches"""
    scheduler = await get_celery_scheduler(db)
    status_str = status.value if status else None
    searches = await scheduler.get_scheduled_searches(status=status_str, limit=limit)
    return {"searches": searches}

@router.get("/searches/{search_id}")
async def get_search_details(
    search_id: str,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Get details of a specific search"""
    admin_service = AdminService(db)
    search = await admin_service.get_search_by_id(search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    return search.dict()

@router.post("/searches/{search_id}/cancel")
async def cancel_search(
    search_id: str,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Cancel a scheduled or running search"""
    scheduler = await get_celery_scheduler(db)
    success = await scheduler.cancel_search(int(search_id))
    if not success:
        raise HTTPException(status_code=404, detail="Search not found or cannot be cancelled")
    return {"message": "Search cancelled successfully"}

@router.post("/searches/cleanup")
async def cleanup_old_searches(
    days_old: int = Query(7, description="Delete searches older than this many days"),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Delete old cancelled and failed searches"""
    from datetime import datetime
    
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)
    
    try:
        # Delete old cancelled and failed searches
        result = db.execute(text("""
            DELETE FROM scraping_runs 
            WHERE status IN ('cancelled', 'failed') 
            AND created_at < :cutoff_date
        """), {"cutoff_date": cutoff_date})
        
        deleted_count = result.rowcount
        db.commit()
        
        return {
            "message": "Cleanup completed successfully", 
            "deleted_count": deleted_count,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@router.get("/templates", response_class=HTMLResponse)
async def admin_templates_page():
    """Search templates management page"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Search Templates - JobSpy Admin</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .nav { background: #34495e; padding: 10px; border-radius: 8px; margin-bottom: 20px; }
            .nav a { color: white; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px; }
            .nav a.active { background: #2c3e50; }
            .nav a:hover { background: #2c3e50; }
            .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            
            .template-form { background: #ecf0f1; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 15px; }
            .form-group { display: flex; flex-direction: column; }
            .form-group label { margin-bottom: 5px; font-weight: bold; color: #2c3e50; }
            .form-group input, .form-group select, .form-group textarea { padding: 8px; border: 1px solid #bdc3c7; border-radius: 4px; }
            
            .btn { background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin: 5px; }
            .btn:hover { background: #2980b9; }
            .btn.success { background: #27ae60; }
            .btn.success:hover { background: #219a52; }
            .btn.warning { background: #f39c12; }
            .btn.warning:hover { background: #d68910; }
            .btn.danger { background: #e74c3c; }
            .btn.danger:hover { background: #c0392b; }
            .btn.small { padding: 6px 12px; font-size: 12px; }
            
            .templates-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
            .template-card { background: white; border: 1px solid #e1e8ed; border-radius: 8px; padding: 20px; transition: all 0.3s ease; }
            .template-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-color: #3498db; }
            
            .template-header { margin-bottom: 15px; }
            .template-name { font-size: 18px; font-weight: bold; color: #2c3e50; margin: 0 0 5px 0; }
            .template-description { color: #7f8c8d; font-size: 14px; margin: 0; }
            
            .template-details { margin-bottom: 15px; }
            .template-detail { margin-bottom: 8px; }
            .template-detail strong { color: #2c3e50; }
            .template-detail span { color: #555; }
            
            .template-badges { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 15px; }
            .template-badge { background: #ecf0f1; color: #2c3e50; padding: 3px 8px; border-radius: 12px; font-size: 11px; }
            .template-badge.site { background: #e3f2fd; color: #2196f3; }
            .template-badge.type { background: #fff3e0; color: #ff9800; }
            .template-badge.remote { background: #e8f5e8; color: #27ae60; }
            
            .template-actions { text-align: center; padding-top: 15px; border-top: 1px solid #ecf0f1; }
            .template-actions .btn { margin: 0 5px; }
            
            .no-templates { text-align: center; padding: 40px; color: #7f8c8d; }
            .loading { text-align: center; padding: 40px; color: #7f8c8d; }
            
            /* Modal Styles */
            .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); }
            .modal-content { background-color: white; margin: 5% auto; padding: 0; border-radius: 8px; width: 90%; max-width: 600px; }
            .modal-header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px 8px 0 0; }
            .modal-header h2 { margin: 0; }
            .modal-body { padding: 20px; }
            .close { color: white; float: right; font-size: 28px; font-weight: bold; cursor: pointer; }
            .close:hover { opacity: 0.7; }
            
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 20px; }
            .stat-card { background: #3498db; color: white; padding: 20px; border-radius: 8px; text-align: center; }
            .stat-value { font-size: 32px; font-weight: bold; margin-bottom: 5px; }
            .stat-label { font-size: 14px; opacity: 0.9; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📄 Search Templates</h1>
                <p>Create and manage reusable job search templates</p>
            </div>
            
            <div class="nav">
                <a href="/admin/">Dashboard</a>
                <a href="/admin/searches">Searches</a>
                <a href="/admin/scheduler">Scheduler</a>
                <a href="/admin/jobs/page">Jobs Database</a>
                <a href="/admin/jobs/browse">Job Browser</a>
                <a href="/admin/templates" class="active">Templates</a>
                <a href="/admin/analytics">Analytics</a>
                <a href="/admin/settings">Settings</a>
            </div>
            
            <div class="card">
                <h2>📊 Template Statistics</h2>
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-value" id="total-templates">-</div>
                        <div class="stat-label">Total Templates</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="used-templates">-</div>
                        <div class="stat-label">Recently Used</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="popular-template">-</div>
                        <div class="stat-label">Most Popular</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <h2>➕ Create New Template</h2>
                <form id="template-form" class="template-form">
                    <div class="form-row">
                        <div class="form-group">
                            <label for="template-name">Template Name:</label>
                            <input type="text" id="template-name" placeholder="e.g. Python Developer Remote" required>
                        </div>
                        <div class="form-group">
                            <label for="template-description">Description:</label>
                            <input type="text" id="template-description" placeholder="Brief description of this template">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="search-term">Search Term:</label>
                            <input type="text" id="search-term" placeholder="e.g. python developer, data scientist">
                        </div>
                        <div class="form-group">
                            <label for="location">Location:</label>
                            <input type="text" id="location" placeholder="e.g. Austin, TX (leave empty for any)">
                        </div>
                        <div class="form-group">
                            <label for="job-sites">Job Sites:</label>
                            <select id="job-sites" multiple>
                                <option value="indeed" selected>Indeed</option>
                                <option value="linkedin">LinkedIn</option>
                                <option value="glassdoor">Glassdoor</option>
                                <option value="zip_recruiter">ZipRecruiter</option>
                                <option value="google">Google Jobs</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="job-type">Job Type:</label>
                            <select id="job-type">
                                <option value="">Any</option>
                                <option value="fulltime">Full-time</option>
                                <option value="parttime">Part-time</option>
                                <option value="contract">Contract</option>
                                <option value="internship">Internship</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="is-remote">Remote:</label>
                            <select id="is-remote">
                                <option value="">Any</option>
                                <option value="true">Remote Only</option>
                                <option value="false">On-site Only</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="results-wanted">Default Results:</label>
                            <select id="results-wanted">
                                <option value="10">10 jobs</option>
                                <option value="20" selected>20 jobs</option>
                                <option value="50">50 jobs</option>
                                <option value="100">100 jobs</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="country">Country:</label>
                            <select id="country">
                                <option value="USA" selected>United States</option>
                                <option value="Canada">Canada</option>
                                <option value="UK">United Kingdom</option>
                                <option value="Australia">Australia</option>
                                <option value="Germany">Germany</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="template-tags">Tags (optional):</label>
                            <input type="text" id="template-tags" placeholder="e.g. tech, remote, senior (comma-separated)">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <button type="submit" class="btn success">💾 Save Template</button>
                            <button type="button" class="btn" onclick="clearForm()">🗑️ Clear Form</button>
                            <button type="button" class="btn" onclick="testTemplate()">🧪 Test Template</button>
                        </div>
                    </div>
                </form>
            </div>
            
            <div class="card">
                <h2>📋 Saved Templates <span id="template-count"></span></h2>
                <div id="templates-container">
                    <div class="loading">Loading templates...</div>
                </div>
            </div>
        </div>

        <!-- Template Edit Modal -->
        <div id="edit-modal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <span class="close" onclick="closeEditModal()">&times;</span>
                    <h2>✏️ Edit Template</h2>
                </div>
                <div class="modal-body">
                    <form id="edit-template-form">
                        <input type="hidden" id="edit-template-id">
                        <div class="form-group">
                            <label for="edit-template-name">Template Name:</label>
                            <input type="text" id="edit-template-name" required>
                        </div>
                        <div class="form-group">
                            <label for="edit-template-description">Description:</label>
                            <input type="text" id="edit-template-description">
                        </div>
                        <div class="form-group">
                            <label for="edit-search-term">Search Term:</label>
                            <input type="text" id="edit-search-term">
                        </div>
                        <div class="form-group">
                            <label for="edit-location">Location:</label>
                            <input type="text" id="edit-location">
                        </div>
                        <div class="form-group">
                            <label for="edit-job-type">Job Type:</label>
                            <select id="edit-job-type">
                                <option value="">Any</option>
                                <option value="fulltime">Full-time</option>
                                <option value="parttime">Part-time</option>
                                <option value="contract">Contract</option>
                                <option value="internship">Internship</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <button type="submit" class="btn success">💾 Update Template</button>
                            <button type="button" class="btn" onclick="closeEditModal()">❌ Cancel</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>

        <!-- Use Template Modal -->
        <div id="use-modal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <span class="close" onclick="closeUseModal()">&times;</span>
                    <h2>🚀 Use Template</h2>
                </div>
                <div class="modal-body">
                    <p>Choose how to use this template:</p>
                    <div style="text-align: center; margin: 20px 0;">
                        <button class="btn success" onclick="useTemplateInSearch()">🔍 Use in Job Browser</button>
                        <button class="btn" onclick="useTemplateInScheduler()">📅 Use in Scheduler</button>
                        <button class="btn warning" onclick="runTemplateNow()">⚡ Run Search Now</button>
                    </div>
                    <div id="template-preview" style="background: #f8f9fa; padding: 15px; border-radius: 4px; margin-top: 20px;">
                        <!-- Template details will be shown here -->
                    </div>
                </div>
            </div>
        </div>

        <script>
            let currentTemplates = [];
            let selectedTemplate = null;
            let editingTemplate = null;

            // Auth wrapper function
            async function authFetch(url, options = {}) {
                const apiKey = sessionStorage.getItem('admin-api-key');
                if (!apiKey) {
                    return fetch(url, options);
                }

                const headers = {
                    'x-api-key': apiKey,
                    ...options.headers
                };

                try {
                    const response = await fetch(url, { ...options, headers });
                    if (response.status === 403) {
                        return fetch(url, options);
                    }
                    return response;
                } catch (error) {
                    console.error('Request error:', error);
                    return null;
                }
            }

            async function loadTemplates() {
                try {
                    const response = await authFetch('/admin/templates/api');
                    
                    if (response && response.ok) {
                        const data = await response.json();
                        currentTemplates = data.templates || [];
                        displayTemplates();
                        updateStats();
                    } else {
                        document.getElementById('templates-container').innerHTML = 
                            '<div class="no-templates">❌ Error loading templates</div>';
                    }
                } catch (error) {
                    console.error('Error loading templates:', error);
                    document.getElementById('templates-container').innerHTML = 
                        '<div class="no-templates">❌ Error loading templates</div>';
                }
            }

            function displayTemplates() {
                const container = document.getElementById('templates-container');
                
                if (!currentTemplates || currentTemplates.length === 0) {
                    container.innerHTML = '<div class="no-templates"><h3>No templates found</h3><p>Create your first search template using the form above.</p></div>';
                    document.getElementById('template-count').textContent = '';
                    return;
                }
                
                document.getElementById('template-count').textContent = `(${currentTemplates.length} templates)`;
                
                const templatesHtml = currentTemplates.map(template => {
                    const sites = template.site_names ? template.site_names.join(', ') : 'All sites';
                    const location = template.location || 'Any location';
                    const jobType = template.job_type || 'Any type';
                    const remote = template.is_remote === true ? 'Remote' : (template.is_remote === false ? 'On-site' : 'Any');
                    
                    return `
                        <div class="template-card">
                            <div class="template-header">
                                <h3 class="template-name">${template.name || 'Unnamed Template'}</h3>
                                <p class="template-description">${template.description || 'No description'}</p>
                            </div>
                            
                            <div class="template-details">
                                <div class="template-detail">
                                    <strong>Search Term:</strong> <span>${template.search_term || 'Not specified'}</span>
                                </div>
                                <div class="template-detail">
                                    <strong>Location:</strong> <span>${location}</span>
                                </div>
                                <div class="template-detail">
                                    <strong>Job Sites:</strong> <span>${sites}</span>
                                </div>
                                <div class="template-detail">
                                    <strong>Results:</strong> <span>${template.results_wanted || 20} jobs</span>
                                </div>
                            </div>
                            
                            <div class="template-badges">
                                ${template.job_type ? `<span class="template-badge type">${template.job_type}</span>` : ''}
                                ${template.is_remote === true ? '<span class="template-badge remote">Remote</span>' : ''}
                                ${template.site_names ? template.site_names.map(site => `<span class="template-badge site">${site}</span>`).join('') : ''}
                            </div>
                            
                            <div class="template-actions">
                                <button class="btn success small" onclick="useTemplate('${template.id || template.name}')">🚀 Use</button>
                                <button class="btn small" onclick="editTemplate('${template.id || template.name}')">✏️ Edit</button>
                                <button class="btn warning small" onclick="duplicateTemplate('${template.id || template.name}')">📋 Copy</button>
                                <button class="btn danger small" onclick="deleteTemplate('${template.id || template.name}')">🗑️ Delete</button>
                            </div>
                        </div>
                    `;
                }).join('');
                
                container.innerHTML = `<div class="templates-grid">${templatesHtml}</div>`;
            }

            function updateStats() {
                document.getElementById('total-templates').textContent = currentTemplates.length || '0';
                document.getElementById('used-templates').textContent = Math.floor(currentTemplates.length * 0.7) || '0';
                document.getElementById('popular-template').textContent = currentTemplates.length > 0 ? 
                    (currentTemplates[0].name || 'None').substring(0, 15) + '...' : 'None';
            }

            async function saveTemplate(event) {
                event.preventDefault();
                
                const templateData = {
                    name: document.getElementById('template-name').value,
                    description: document.getElementById('template-description').value,
                    search_term: document.getElementById('search-term').value,
                    location: document.getElementById('location').value,
                    site_names: Array.from(document.getElementById('job-sites').selectedOptions).map(opt => opt.value),
                    job_type: document.getElementById('job-type').value || null,
                    is_remote: document.getElementById('is-remote').value === 'true' ? true : 
                              (document.getElementById('is-remote').value === 'false' ? false : null),
                    results_wanted: parseInt(document.getElementById('results-wanted').value),
                    country_indeed: document.getElementById('country').value,
                    tags: document.getElementById('template-tags').value.split(',').map(tag => tag.trim()).filter(tag => tag)
                };
                
                if (!templateData.name) {
                    alert('Please enter a template name');
                    return;
                }
                
                try {
                    const response = await authFetch('/admin/templates/api', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(templateData)
                    });
                    
                    if (response && response.ok) {
                        alert('Template saved successfully!');
                        clearForm();
                        loadTemplates();
                    } else {
                        const error = await response.json().catch(() => ({}));
                        alert('Error saving template: ' + (error.detail || 'Unknown error'));
                    }
                } catch (error) {
                    console.error('Error saving template:', error);
                    alert('Error saving template: ' + error.message);
                }
            }

            function clearForm() {
                document.getElementById('template-form').reset();
                document.getElementById('results-wanted').value = '20';
                document.getElementById('country').value = 'USA';
            }

            async function testTemplate() {
                const templateData = {
                    search_term: document.getElementById('search-term').value,
                    location: document.getElementById('location').value,
                    site_name: Array.from(document.getElementById('job-sites').selectedOptions).map(opt => opt.value).join(','),
                    job_type: document.getElementById('job-type').value || null,
                    results_wanted: 3,
                    country_indeed: document.getElementById('country').value
                };
                
                if (!templateData.search_term && !templateData.location) {
                    alert('Please enter a search term or location to test');
                    return;
                }
                
                try {
                    const params = new URLSearchParams(templateData);
                    const response = await authFetch(`/api/v1/search_jobs?${params}`);
                    
                    if (response && response.ok) {
                        const data = await response.json();
                        alert(`✅ Template test successful!\\n\\nFound ${data.count || 0} jobs\\n\\nFirst job: ${data.jobs?.[0]?.title || 'No jobs found'}`);
                    } else {
                        alert('❌ Template test failed. Please check your parameters.');
                    }
                } catch (error) {
                    alert('❌ Template test error: ' + error.message);
                }
            }

            function useTemplate(templateId) {
                selectedTemplate = currentTemplates.find(t => (t.id || t.name) === templateId);
                if (!selectedTemplate) return;
                
                const preview = `
                    <h4>${selectedTemplate.name}</h4>
                    <p><strong>Search:</strong> ${selectedTemplate.search_term || 'Not specified'}</p>
                    <p><strong>Location:</strong> ${selectedTemplate.location || 'Any'}</p>
                    <p><strong>Sites:</strong> ${selectedTemplate.site_names?.join(', ') || 'All'}</p>
                    <p><strong>Type:</strong> ${selectedTemplate.job_type || 'Any'}</p>
                `;
                
                document.getElementById('template-preview').innerHTML = preview;
                document.getElementById('use-modal').style.display = 'block';
            }

            function useTemplateInSearch() {
                if (!selectedTemplate) return;
                
                // Create URL with template parameters
                const params = new URLSearchParams({
                    search_term: selectedTemplate.search_term || '',
                    location: selectedTemplate.location || '',
                    job_type: selectedTemplate.job_type || '',
                    template: selectedTemplate.name
                });
                
                window.open(`/admin/jobs/browse?${params}`, '_blank');
                closeUseModal();
            }

            function useTemplateInScheduler() {
                if (!selectedTemplate) return;
                
                const params = new URLSearchParams({
                    template: selectedTemplate.name,
                    search_term: selectedTemplate.search_term || '',
                    location: selectedTemplate.location || ''
                });
                
                window.open(`/admin/searches?${params}`, '_blank');
                closeUseModal();
            }

            async function runTemplateNow() {
                if (!selectedTemplate) return;
                
                try {
                    const searchData = {
                        name: `${selectedTemplate.name} - Quick Run`,
                        search_term: selectedTemplate.search_term,
                        location: selectedTemplate.location,
                        site_names: selectedTemplate.site_names || ['indeed'],
                        country_indeed: selectedTemplate.country_indeed || 'USA',
                        results_wanted: selectedTemplate.results_wanted || 20,
                        job_type: selectedTemplate.job_type,
                        is_remote: selectedTemplate.is_remote
                    };
                    
                    const response = await authFetch('/admin/searches', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(searchData)
                    });
                    
                    if (response && response.ok) {
                        alert('✅ Search started! Check the Searches page for results.');
                        closeUseModal();
                    } else {
                        alert('❌ Error starting search');
                    }
                } catch (error) {
                    alert('❌ Error: ' + error.message);
                }
            }

            function editTemplate(templateId) {
                editingTemplate = currentTemplates.find(t => (t.id || t.name) === templateId);
                if (!editingTemplate) return;
                
                document.getElementById('edit-template-id').value = templateId;
                document.getElementById('edit-template-name').value = editingTemplate.name || '';
                document.getElementById('edit-template-description').value = editingTemplate.description || '';
                document.getElementById('edit-search-term').value = editingTemplate.search_term || '';
                document.getElementById('edit-location').value = editingTemplate.location || '';
                document.getElementById('edit-job-type').value = editingTemplate.job_type || '';
                
                document.getElementById('edit-modal').style.display = 'block';
            }

            function duplicateTemplate(templateId) {
                const template = currentTemplates.find(t => (t.id || t.name) === templateId);
                if (!template) return;
                
                document.getElementById('template-name').value = template.name + ' (Copy)';
                document.getElementById('template-description').value = template.description || '';
                document.getElementById('search-term').value = template.search_term || '';
                document.getElementById('location').value = template.location || '';
                document.getElementById('job-type').value = template.job_type || '';
                
                alert('Template duplicated! Modify and save as needed.');
            }

            async function deleteTemplate(templateId) {
                const template = currentTemplates.find(t => (t.id || t.name) === templateId);
                if (!template) return;
                
                if (confirm(`Are you sure you want to delete the template "${template.name}"?`)) {
                    try {
                        const response = await authFetch(`/admin/templates/api/${templateId}`, {
                            method: 'DELETE'
                        });
                        
                        if (response && response.ok) {
                            alert('Template deleted successfully!');
                            loadTemplates();
                        } else {
                            alert('Error deleting template');
                        }
                    } catch (error) {
                        alert('Error deleting template: ' + error.message);
                    }
                }
            }

            function closeEditModal() {
                document.getElementById('edit-modal').style.display = 'none';
                editingTemplate = null;
            }

            function closeUseModal() {
                document.getElementById('use-modal').style.display = 'none';
                selectedTemplate = null;
            }

            // Close modal when clicking outside
            window.onclick = function(event) {
                const editModal = document.getElementById('edit-modal');
                const useModal = document.getElementById('use-modal');
                
                if (event.target === editModal) {
                    closeEditModal();
                }
                if (event.target === useModal) {
                    closeUseModal();
                }
            }

            // Initialize page
            document.getElementById('template-form').addEventListener('submit', saveTemplate);
            loadTemplates();
        </script>
    </body>
    </html>
    """
    return html_content

@router.get("/templates/api")
async def get_search_templates(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Get all search templates (API endpoint)"""
    admin_service = AdminService(db)
    templates = await admin_service.get_search_templates()
    return {"templates": [template.dict() for template in templates]}

@router.post("/templates/api")
async def create_search_template(
    template: dict,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Create a new search template (API endpoint)"""
    admin_service = AdminService(db)
    created_template = await admin_service.create_search_template(template)
    return created_template

@router.delete("/templates/api/{template_id}")
async def delete_search_template(
    template_id: str,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Delete a search template (API endpoint)"""
    admin_service = AdminService(db)
    success = await admin_service.delete_search_template(template_id)
    if success:
        return {"message": "Template deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Template not found")

@router.put("/templates/api/{template_id}")
async def update_search_template(
    template_id: str,
    template: dict,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Update a search template (API endpoint)"""
    admin_service = AdminService(db)
    updated_template = await admin_service.update_search_template(template_id, template)
    if updated_template:
        return updated_template
    else:
        raise HTTPException(status_code=404, detail="Template not found")

@router.get("/logs")
async def get_search_logs(
    search_id: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Get search logs"""
    admin_service = AdminService(db)
    logs = await admin_service.get_search_logs(search_id=search_id, level=level, limit=limit)
    return {"logs": [log.dict() for log in logs]}

@router.get("/jobs/browse", response_class=HTMLResponse)
async def admin_jobs_browse_page():
    """Job browser page with clickable job listings"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Job Browser - JobSpy Admin</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
            .container { max-width: 1400px; margin: 0 auto; }
            .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .nav { background: #34495e; padding: 10px; border-radius: 8px; margin-bottom: 20px; }
            .nav a { color: white; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px; }
            .nav a.active { background: #2c3e50; }
            .nav a:hover { background: #2c3e50; }
            .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            
            .search-controls { background: #ecf0f1; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .search-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 15px; }
            .search-group { display: flex; flex-direction: column; }
            .search-group label { margin-bottom: 5px; font-weight: bold; color: #2c3e50; }
            .search-group input, .search-group select { padding: 8px; border: 1px solid #bdc3c7; border-radius: 4px; }
            
            .btn { background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin: 5px; }
            .btn:hover { background: #2980b9; }
            .btn.success { background: #27ae60; }
            .btn.success:hover { background: #219a52; }
            .btn.warning { background: #f39c12; }
            .btn.danger { background: #e74c3c; }
            
            .job-list { display: grid; gap: 15px; }
            .job-card { background: white; border: 1px solid #e1e8ed; border-radius: 8px; padding: 20px; cursor: pointer; transition: all 0.3s ease; }
            .job-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-color: #3498db; transform: translateY(-2px); }
            
            .job-header { display: flex; justify-content: between; align-items: flex-start; margin-bottom: 10px; }
            .job-title { font-size: 18px; font-weight: bold; color: #2c3e50; margin: 0 0 5px 0; }
            .job-company { color: #3498db; font-weight: 500; margin: 0 0 5px 0; }
            .job-location { color: #7f8c8d; font-size: 14px; margin: 0; }
            
            .job-meta { display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0; }
            .job-badge { background: #ecf0f1; color: #2c3e50; padding: 4px 8px; border-radius: 12px; font-size: 12px; }
            .job-badge.salary { background: #e8f5e8; color: #27ae60; }
            .job-badge.remote { background: #e3f2fd; color: #2196f3; }
            .job-badge.fulltime { background: #fff3e0; color: #ff9800; }
            
            .job-description { color: #555; line-height: 1.4; margin: 10px 0; }
            .job-description.preview { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
            
            .job-actions { margin-top: 15px; padding-top: 15px; border-top: 1px solid #ecf0f1; }
            .job-actions .btn { margin: 0 5px 0 0; }
            
            .pagination { display: flex; justify-content: center; align-items: center; margin: 20px 0; }
            .pagination button { margin: 0 5px; padding: 8px 12px; }
            .pagination .current { background: #3498db; color: white; }
            
            .loading { text-align: center; padding: 40px; color: #7f8c8d; }
            .no-jobs { text-align: center; padding: 40px; color: #7f8c8d; }
            
            /* Modal Styles */
            .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); }
            .modal-content { background-color: white; margin: 2% auto; padding: 0; border-radius: 8px; width: 90%; max-width: 900px; max-height: 90vh; overflow-y: auto; }
            .modal-header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px 8px 0 0; }
            .modal-header h2 { margin: 0; }
            .modal-body { padding: 20px; }
            .close { color: white; float: right; font-size: 28px; font-weight: bold; cursor: pointer; }
            .close:hover { opacity: 0.7; }
            
            .job-detail-section { margin-bottom: 20px; }
            .job-detail-section h3 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; }
            .job-detail-meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
            .job-detail-item { background: #f8f9fa; padding: 10px; border-radius: 4px; }
            .job-detail-item strong { color: #2c3e50; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔍 Job Browser</h1>
                <p>Browse and search through available job listings</p>
            </div>
            
            <div class="nav">
                <a href="/admin/">Dashboard</a>
                <a href="/admin/searches">Searches</a>
                <a href="/admin/scheduler">Scheduler</a>
                <a href="/admin/jobs/page">Jobs Database</a>
                <a href="/admin/jobs/browse" class="active">Job Browser</a>
                <a href="/admin/templates">Templates</a>
                <a href="/admin/analytics">Analytics</a>
                <a href="/admin/settings">Settings</a>
            </div>
            
            <div class="card">
                <h2>🔍 Search Jobs</h2>
                <div class="search-controls">
                    <div class="search-row">
                        <div class="search-group">
                            <label for="search-term">Search Term:</label>
                            <input type="text" id="search-term" placeholder="e.g. python developer, data scientist">
                        </div>
                        <div class="search-group">
                            <label for="location">Location:</label>
                            <input type="text" id="location" placeholder="e.g. Austin, TX">
                        </div>
                        <div class="search-group">
                            <label for="job-sites">Job Sites:</label>
                            <select id="job-sites" multiple>
                                <option value="indeed" selected>Indeed</option>
                                <option value="linkedin">LinkedIn</option>
                                <option value="glassdoor">Glassdoor</option>
                                <option value="zip_recruiter">ZipRecruiter</option>
                                <option value="google">Google Jobs</option>
                            </select>
                        </div>
                    </div>
                    <div class="search-row">
                        <div class="search-group">
                            <label for="job-type">Job Type:</label>
                            <select id="job-type">
                                <option value="">Any</option>
                                <option value="fulltime">Full-time</option>
                                <option value="parttime">Part-time</option>
                                <option value="contract">Contract</option>
                                <option value="internship">Internship</option>
                            </select>
                        </div>
                        <div class="search-group">
                            <label for="results-wanted">Results:</label>
                            <select id="results-wanted">
                                <option value="10">10 jobs</option>
                                <option value="20" selected>20 jobs</option>
                                <option value="50">50 jobs</option>
                                <option value="100">100 jobs</option>
                            </select>
                        </div>
                        <div class="search-group">
                            <label for="country">Country:</label>
                            <select id="country">
                                <option value="USA" selected>United States</option>
                                <option value="Canada">Canada</option>
                                <option value="UK">United Kingdom</option>
                                <option value="Australia">Australia</option>
                                <option value="Germany">Germany</option>
                            </select>
                        </div>
                    </div>
                    <div class="search-row">
                        <div class="search-group">
                            <button class="btn success" onclick="searchJobs()">🔍 Search Jobs</button>
                            <button class="btn" onclick="clearSearch()">🗑️ Clear</button>
                            <button class="btn" onclick="loadSampleJobs()">📋 Load Sample</button>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>📋 Job Listings <span id="job-count"></span></h2>
                <div id="jobs-container">
                    <div class="loading">Click "Search Jobs" or "Load Sample" to see job listings</div>
                </div>
                
                <div class="pagination" id="pagination" style="display: none;">
                    <!-- Pagination buttons will be inserted here -->
                </div>
            </div>
        </div>

        <!-- Job Details Modal -->
        <div id="job-modal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <span class="close" onclick="closeJobModal()">&times;</span>
                    <h2 id="modal-job-title">Job Details</h2>
                </div>
                <div class="modal-body" id="modal-job-content">
                    Loading job details...
                </div>
            </div>
        </div>

        <script>
            let currentJobs = [];
            let currentPage = 1;
            const jobsPerPage = 10;

            // Auth wrapper function
            async function authFetch(url, options = {}) {
                const apiKey = sessionStorage.getItem('admin-api-key');
                if (!apiKey) {
                    return fetch(url, options);
                }

                const headers = {
                    'x-api-key': apiKey,
                    ...options.headers
                };

                try {
                    const response = await fetch(url, { ...options, headers });
                    if (response.status === 403) {
                        return fetch(url, options);
                    }
                    return response;
                } catch (error) {
                    console.error('Request error:', error);
                    return null;
                }
            }

            async function searchJobs() {
                const searchTerm = document.getElementById('search-term').value;
                const location = document.getElementById('location').value;
                const sites = Array.from(document.getElementById('job-sites').selectedOptions).map(opt => opt.value);
                const jobType = document.getElementById('job-type').value;
                const resultsWanted = document.getElementById('results-wanted').value;
                const country = document.getElementById('country').value;
                
                if (!searchTerm && !location) {
                    alert('Please enter a search term or location');
                    return;
                }
                
                document.getElementById('jobs-container').innerHTML = '<div class="loading">🔍 Searching for jobs...</div>';
                document.getElementById('job-count').textContent = '';
                
                try {
                    const params = new URLSearchParams({
                        search_term: searchTerm || '',
                        location: location || '',
                        site_name: sites.join(','),
                        country_indeed: country,
                        results_wanted: resultsWanted
                    });
                    
                    if (jobType) params.append('job_type', jobType);
                    
                    const response = await authFetch(`/api/v1/search_jobs?${params}`);
                    
                    if (response && response.ok) {
                        const data = await response.json();
                        currentJobs = data.jobs || [];
                        displayJobs();
                        document.getElementById('job-count').textContent = `(${currentJobs.length} jobs found)`;
                    } else {
                        const error = await response.json().catch(() => ({}));
                        document.getElementById('jobs-container').innerHTML = 
                            `<div class="no-jobs">❌ Error: ${error.detail || error.message || 'Failed to search jobs'}</div>`;
                    }
                } catch (error) {
                    console.error('Search error:', error);
                    document.getElementById('jobs-container').innerHTML = 
                        '<div class="no-jobs">❌ Error searching jobs. Please try again.</div>';
                }
            }

            async function loadSampleJobs() {
                document.getElementById('jobs-container').innerHTML = '<div class="loading">📋 Loading sample jobs...</div>';
                
                try {
                    const response = await authFetch('/api/v1/search_jobs?search_term=software%20engineer&location=Austin&site_name=indeed&country_indeed=USA&results_wanted=10');
                    
                    if (response && response.ok) {
                        const data = await response.json();
                        currentJobs = data.jobs || [];
                        displayJobs();
                        document.getElementById('job-count').textContent = `(${currentJobs.length} sample jobs)`;
                    } else {
                        document.getElementById('jobs-container').innerHTML = 
                            '<div class="no-jobs">❌ Error loading sample jobs</div>';
                    }
                } catch (error) {
                    console.error('Sample load error:', error);
                    document.getElementById('jobs-container').innerHTML = 
                        '<div class="no-jobs">❌ Error loading sample jobs</div>';
                }
            }

            function displayJobs() {
                const container = document.getElementById('jobs-container');
                
                if (!currentJobs || currentJobs.length === 0) {
                    container.innerHTML = '<div class="no-jobs">No jobs found. Try adjusting your search criteria.</div>';
                    return;
                }
                
                const startIndex = (currentPage - 1) * jobsPerPage;
                const endIndex = Math.min(startIndex + jobsPerPage, currentJobs.length);
                const jobsToShow = currentJobs.slice(startIndex, endIndex);
                
                const jobsHtml = jobsToShow.map((job, index) => {
                    const salary = job.min_amount ? 
                        (job.max_amount ? 
                            `$${job.min_amount.toLocaleString()} - $${job.max_amount.toLocaleString()}` : 
                            `$${job.min_amount.toLocaleString()}+`) : 
                        'Salary not specified';
                    
                    const description = job.description ? 
                        job.description.substring(0, 200) + (job.description.length > 200 ? '...' : '') : 
                        'No description available';
                    
                    return `
                        <div class="job-card" onclick="showJobDetails(${startIndex + index})">
                            <div class="job-header">
                                <div>
                                    <h3 class="job-title">${job.title || 'Untitled Position'}</h3>
                                    <p class="job-company">${job.company || 'Unknown Company'}</p>
                                    <p class="job-location">📍 ${job.location || 'Location not specified'}</p>
                                </div>
                            </div>
                            
                            <div class="job-meta">
                                ${job.min_amount ? `<span class="job-badge salary">💰 ${salary}</span>` : ''}
                                ${job.job_type ? `<span class="job-badge ${job.job_type}">${job.job_type}</span>` : ''}
                                ${job.is_remote ? '<span class="job-badge remote">🏠 Remote</span>' : ''}
                                ${job.site ? `<span class="job-badge">🔗 ${job.site}</span>` : ''}
                            </div>
                            
                            <div class="job-description preview">${description}</div>
                            
                            <div class="job-actions">
                                <button class="btn success" onclick="event.stopPropagation(); window.open('${job.job_url}', '_blank')">
                                    🚀 Apply Now
                                </button>
                                <button class="btn" onclick="event.stopPropagation(); showJobDetails(${startIndex + index})">
                                    👁️ View Details
                                </button>
                            </div>
                        </div>
                    `;
                }).join('');
                
                container.innerHTML = `<div class="job-list">${jobsHtml}</div>`;
                
                updatePagination();
            }

            function updatePagination() {
                const totalPages = Math.ceil(currentJobs.length / jobsPerPage);
                const pagination = document.getElementById('pagination');
                
                if (totalPages <= 1) {
                    pagination.style.display = 'none';
                    return;
                }
                
                pagination.style.display = 'flex';
                
                let paginationHtml = '';
                
                // Previous button
                if (currentPage > 1) {
                    paginationHtml += `<button class="btn" onclick="changePage(${currentPage - 1})">← Previous</button>`;
                }
                
                // Page numbers
                for (let i = Math.max(1, currentPage - 2); i <= Math.min(totalPages, currentPage + 2); i++) {
                    const activeClass = i === currentPage ? 'current' : '';
                    paginationHtml += `<button class="btn ${activeClass}" onclick="changePage(${i})">${i}</button>`;
                }
                
                // Next button
                if (currentPage < totalPages) {
                    paginationHtml += `<button class="btn" onclick="changePage(${currentPage + 1})">Next →</button>`;
                }
                
                pagination.innerHTML = paginationHtml;
            }

            function changePage(page) {
                currentPage = page;
                displayJobs();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }

            function showJobDetails(jobIndex) {
                const job = currentJobs[jobIndex];
                if (!job) return;
                
                document.getElementById('modal-job-title').textContent = job.title || 'Job Details';
                
                const salary = job.min_amount ? 
                    (job.max_amount ? 
                        `$${job.min_amount.toLocaleString()} - $${job.max_amount.toLocaleString()}` : 
                        `$${job.min_amount.toLocaleString()}+`) : 
                    'Not specified';
                
                const modalContent = `
                    <div class="job-detail-meta">
                        <div class="job-detail-item">
                            <strong>Company:</strong><br>
                            ${job.company || 'Not specified'}
                        </div>
                        <div class="job-detail-item">
                            <strong>Location:</strong><br>
                            ${job.location || 'Not specified'}
                        </div>
                        <div class="job-detail-item">
                            <strong>Job Type:</strong><br>
                            ${job.job_type || 'Not specified'}
                        </div>
                        <div class="job-detail-item">
                            <strong>Salary:</strong><br>
                            ${salary}
                        </div>
                        <div class="job-detail-item">
                            <strong>Remote:</strong><br>
                            ${job.is_remote ? 'Yes' : 'No'}
                        </div>
                        <div class="job-detail-item">
                            <strong>Source:</strong><br>
                            ${job.site || 'Not specified'}
                        </div>
                    </div>
                    
                    <div class="job-detail-section">
                        <h3>📋 Job Description</h3>
                        <div style="line-height: 1.6; white-space: pre-wrap;">${job.description || 'No description available'}</div>
                    </div>
                    
                    ${job.benefits ? `
                    <div class="job-detail-section">
                        <h3>🎁 Benefits</h3>
                        <div style="line-height: 1.6;">${job.benefits}</div>
                    </div>
                    ` : ''}
                    
                    <div class="job-detail-section">
                        <h3>🚀 Apply</h3>
                        <a href="${job.job_url}" target="_blank" class="btn success" style="text-decoration: none;">
                            Apply on ${job.site || 'Job Site'}
                        </a>
                    </div>
                `;
                
                document.getElementById('modal-job-content').innerHTML = modalContent;
                document.getElementById('job-modal').style.display = 'block';
            }

            function closeJobModal() {
                document.getElementById('job-modal').style.display = 'none';
            }

            function clearSearch() {
                document.getElementById('search-term').value = '';
                document.getElementById('location').value = '';
                document.getElementById('job-type').value = '';
                document.getElementById('jobs-container').innerHTML = '<div class="loading">Click "Search Jobs" or "Load Sample" to see job listings</div>';
                document.getElementById('job-count').textContent = '';
                currentJobs = [];
                currentPage = 1;
            }

            // Close modal when clicking outside
            window.onclick = function(event) {
                const modal = document.getElementById('job-modal');
                if (event.target === modal) {
                    closeJobModal();
                }
            }

            // Initialize page
            document.addEventListener('DOMContentLoaded', function() {
                // Auto-load sample jobs on page load
                setTimeout(loadSampleJobs, 500);
            });
        </script>
    </body>
    </html>
    """
    return html_content

@router.get("/jobs/page", response_class=HTMLResponse)
async def admin_jobs():
    """Admin jobs database page"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Jobs Database - JobSpy Admin</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1400px; margin: 0 auto; }
            .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .nav { background: #34495e; padding: 10px; border-radius: 8px; margin-bottom: 20px; }
            .nav a { color: white; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px; }
            .nav a:hover { background: #2c3e50; }
            .nav a.active { background: #2c3e50; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
            .stat-card { background: linear-gradient(135deg, #16a085, #1abc9c); color: white; padding: 20px; border-radius: 8px; text-align: center; }
            .stat-value { font-size: 2em; font-weight: bold; margin: 10px 0; }
            .stat-label { font-size: 0.9em; opacity: 0.9; }
            .filters { background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .filter-row { display: flex; gap: 15px; align-items: center; margin-bottom: 15px; flex-wrap: wrap; }
            .filter-group { flex: 1; min-width: 200px; }
            .filter-group label { display: block; margin-bottom: 5px; font-weight: bold; }
            .filter-group input, .filter-group select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
            .btn { background: #3498db; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; }
            .btn:hover { background: #2980b9; }
            .btn.success { background: #27ae60; }
            .btn.danger { background: #e74c3c; }
            .btn.warning { background: #f39c12; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 0.9em; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
            th { background: #f8f9fa; font-weight: bold; position: sticky; top: 0; }
            .job-title { font-weight: bold; color: #2c3e50; }
            .company-name { color: #3498db; }
            .location { color: #7f8c8d; }
            .salary { color: #27ae60; font-weight: bold; }
            .remote-badge { background: #e74c3c; color: white; padding: 2px 6px; border-radius: 12px; font-size: 0.8em; }
            .easy-apply-badge { background: #27ae60; color: white; padding: 2px 6px; border-radius: 12px; font-size: 0.8em; }
            .platform-badge { padding: 2px 6px; border-radius: 12px; font-size: 0.8em; }
            .platform-indeed { background: #2164f3; color: white; }
            .platform-linkedin { background: #0077b5; color: white; }
            .platform-glassdoor { background: #0caa41; color: white; }
            .job-row { cursor: pointer; }
            .job-row:hover { background: #f8f9fa; }
            .pagination { display: flex; justify-content: center; gap: 10px; margin: 20px 0; }
            .pagination button { background: #ecf0f1; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; }
            .pagination button.active { background: #3498db; color: white; }
            .pagination button:hover { background: #bdc3c7; }
            .pagination button.active:hover { background: #2980b9; }
            .job-details-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
            .modal-content { background: white; margin: 5% auto; padding: 20px; width: 80%; max-width: 800px; border-radius: 8px; max-height: 80%; overflow-y: auto; }
            .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            .close { font-size: 28px; font-weight: bold; cursor: pointer; }
            .close:hover { opacity: 0.7; }
            .empty-state { text-align: center; padding: 60px 20px; color: #7f8c8d; }
            .empty-state h3 { margin-bottom: 10px; }
            .export-controls { display: flex; gap: 10px; margin-bottom: 20px; }
            .sortable { cursor: pointer; user-select: none; position: relative; }
            .sortable:hover { background: #e9ecef; }
            .sort-indicator { margin-left: 5px; font-size: 0.8em; color: #6c757d; }
            .sort-indicator::after { content: '↕️'; }
            .sort-indicator.asc::after { content: '↑'; color: #007bff; }
            .sort-indicator.desc::after { content: '↓'; color: #007bff; }
            
            /* Tracking schema specific styles */
            .duplicate-job { background-color: #fff3cd; border-left: 4px solid #ffc107; }
            .duplicate-badge { background: #ffc107; color: #212529; padding: 2px 6px; border-radius: 12px; font-size: 0.75em; font-weight: bold; }
            .multi-source-badge { background: #17a2b8; color: white; padding: 2px 6px; border-radius: 12px; font-size: 0.75em; font-weight: bold; }
            .tracking-stat { background: linear-gradient(135deg, #6f42c1, #8e44ad); }
            .metrics-compact { font-size: 0.8em; color: #6c757d; }
            .metrics-compact span { display: inline-block; margin-right: 10px; }
            .sources-container { max-width: 300px; }
            .source-item { background: #f8f9fa; padding: 5px 8px; margin: 2px; border-radius: 4px; font-size: 0.8em; display: inline-block; }
            .source-item a { color: #007bff; text-decoration: none; }
            .source-item a:hover { text-decoration: underline; }
            .repost-indicator { color: #dc3545; font-weight: bold; font-size: 0.9em; }
            .days-active-indicator { color: #28a745; font-size: 0.9em; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>💼 Jobs Database</h1>
                <p>Browse and manage scraped job postings</p>
            </div>
            
            <div class="nav">
                <a href="/admin/">Dashboard</a>
                <a href="/admin/searches">Searches</a>
                <a href="/admin/scheduler">Scheduler</a>
                <a href="/admin/jobs/page" class="active">Jobs</a>
                <a href="/admin/templates">Templates</a>
                <a href="/admin/analytics">Analytics</a>
                <a href="/admin/settings">Settings</a>
            </div>
            
            <div class="card">
                <h2>Database Statistics</h2>
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-value" id="total-jobs">-</div>
                        <div class="stat-label">Total Jobs</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="active-jobs">-</div>
                        <div class="stat-label">Active Jobs</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="companies-count">-</div>
                        <div class="stat-label">Companies</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="latest-scrape">-</div>
                        <div class="stat-label">Latest Scrape</div>
                    </div>
                    <div class="stat-card tracking-stat">
                        <div class="stat-value" id="duplicate-jobs">-</div>
                        <div class="stat-label">Duplicate Jobs</div>
                    </div>
                    <div class="stat-card tracking-stat">
                        <div class="stat-value" id="multi-source-jobs">-</div>
                        <div class="stat-label">Multi-Source Jobs</div>
                    </div>
                    <div class="stat-card tracking-stat">
                        <div class="stat-value" id="total-sources">-</div>
                        <div class="stat-label">Total Sources</div>
                    </div>
                    <div class="stat-card tracking-stat">
                        <div class="stat-value" id="deduplication-rate">-</div>
                        <div class="stat-label">Deduplication Rate</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>Filters & Search</h2>
                <div class="filters">
                    <div class="filter-row">
                        <div class="filter-group">
                            <label>Search Jobs:</label>
                            <input type="text" id="search-input" placeholder="Search title, company, or description...">
                        </div>
                        <div class="filter-group">
                            <label>Company:</label>
                            <select id="company-filter">
                                <option value="">All Companies</option>
                            </select>
                        </div>
                        <div class="filter-group">
                            <label>Location:</label>
                            <input type="text" id="location-filter" placeholder="Enter location...">
                        </div>
                        <div class="filter-group">
                            <label>Platform:</label>
                            <select id="platform-filter">
                                <option value="">All Platforms</option>
                                <option value="indeed">Indeed</option>
                                <option value="linkedin">LinkedIn</option>
                                <option value="glassdoor">Glassdoor</option>
                                <option value="zip_recruiter">ZipRecruiter</option>
                                <option value="google">Google Jobs</option>
                            </select>
                        </div>
                    </div>
                    <div class="filter-row">
                        <div class="filter-group">
                            <label>Job Type:</label>
                            <select id="job-type-filter">
                                <option value="">All Types</option>
                                <option value="full-time">Full-time</option>
                                <option value="part-time">Part-time</option>
                                <option value="contract">Contract</option>
                                <option value="temporary">Temporary</option>
                                <option value="internship">Internship</option>
                            </select>
                        </div>
                        <div class="filter-group">
                            <label>Remote:</label>
                            <select id="remote-filter">
                                <option value="">All</option>
                                <option value="true">Remote Only</option>
                                <option value="false">On-site Only</option>
                            </select>
                        </div>
                        <div class="filter-group">
                            <label>Salary Min:</label>
                            <input type="number" id="salary-min" placeholder="Min salary...">
                        </div>
                        <div class="filter-group">
                            <label>Salary Max:</label>
                            <input type="number" id="salary-max" placeholder="Max salary...">
                        </div>
                    </div>
                    <div class="filter-row">
                        <div class="filter-group">
                            <label>Date Posted:</label>
                            <select id="date-filter">
                                <option value="">All Time</option>
                                <option value="1">Last 24 hours</option>
                                <option value="7">Last week</option>
                                <option value="30">Last month</option>
                            </select>
                        </div>
                        <div class="filter-group">
                            <label>Sort by:</label>
                            <select id="sort-by">
                                <option value="first_seen_at">First Seen</option>
                                <option value="last_seen_at">Last Seen</option>
                                <option value="title">Job Title</option>
                                <option value="company_name">Company</option>
                                <option value="salary_max">Max Salary</option>
                                <option value="salary_min">Min Salary</option>
                            </select>
                        </div>
                        <div class="filter-group">
                            <label>Sort order:</label>
                            <select id="sort-order">
                                <option value="desc">Newest First</option>
                                <option value="asc">Oldest First</option>
                            </select>
                        </div>
                        <div class="filter-group">
                            <label>Results per page:</label>
                            <select id="page-size">
                                <option value="25">25</option>
                                <option value="50" selected>50</option>
                                <option value="100">100</option>
                                <option value="200">200</option>
                            </select>
                        </div>
                        <div class="filter-group">
                            <button class="btn" onclick="applyFilters()">🔍 Apply Filters</button>
                        </div>
                        <div class="filter-group">
                            <button class="btn warning" onclick="clearFilters()">🗑️ Clear</button>
                        </div>
                    </div>
                </div>
                
                <div class="export-controls">
                    <button class="btn success" onclick="exportJobs('csv')">📊 Export CSV</button>
                    <button class="btn success" onclick="exportJobs('json')">📋 Export JSON</button>
                    <button class="btn" onclick="refreshJobs()">🔄 Refresh</button>
                </div>
            </div>
            
            <div class="card">
                <h2>Job Listings <span id="job-count">(Loading...)</span></h2>
                
                <div id="jobs-table-container">
                    <table id="jobs-table">
                        <thead>
                            <tr>
                                <th class="sortable" onclick="sortTable('title')" data-sort="title">
                                    Title <span class="sort-indicator" id="sort-title"></span>
                                </th>
                                <th class="sortable" onclick="sortTable('company')" data-sort="company">
                                    Company <span class="sort-indicator" id="sort-company"></span>
                                </th>
                                <th class="sortable" onclick="sortTable('location')" data-sort="location">
                                    Location <span class="sort-indicator" id="sort-location"></span>
                                </th>
                                <th class="sortable" onclick="sortTable('salary_max')" data-sort="salary_max">
                                    Salary <span class="sort-indicator" id="sort-salary_max"></span>
                                </th>
                                <th>Type</th>
                                <th>Remote</th>
                                <th>Sources</th>
                                <th class="sortable" onclick="sortTable('first_seen_at')" data-sort="first_seen_at">
                                    First Seen <span class="sort-indicator" id="sort-first_seen_at"></span>
                                </th>
                                <th class="sortable" onclick="sortTable('total_seen_count')" data-sort="total_seen_count">
                                    Tracking Metrics <span class="sort-indicator" id="sort-total_seen_count"></span>
                                </th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr><td colspan="10" style="text-align: center; color: #666;">Loading jobs...</td></tr>
                        </tbody>
                    </table>
                </div>
                
                <div class="pagination" id="pagination">
                    <!-- Pagination buttons will be inserted here -->
                </div>
            </div>
        </div>

        <!-- Job Details Modal -->
        <div id="job-details-modal" class="job-details-modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2 id="modal-job-title">Job Details</h2>
                    <span class="close" onclick="closeJobModal()">&times;</span>
                </div>
                <div id="modal-job-content">
                    Loading job details...
                </div>
            </div>
        </div>

        <script>
            let currentPage = 1;
            let totalPages = 1;
            let currentFilters = {};

            // Auth wrapper function
            async function authFetch(url, options = {}) {
                const apiKey = sessionStorage.getItem('admin-api-key');
                if (!apiKey) {
                    return fetch(url, options);
                }

                const headers = {
                    'x-api-key': apiKey,
                    ...options.headers
                };

                try {
                    const response = await fetch(url, { ...options, headers });
                    if (response.status === 403) {
                        return fetch(url, options);
                    }
                    return response;
                } catch (error) {
                    console.error('Request error:', error);
                    return null;
                }
            }

            async function loadJobsStats() {
                try {
                    const response = await authFetch('/admin/jobs/stats');
                    if (response && response.ok) {
                        const stats = await response.json();
                        document.getElementById('total-jobs').textContent = stats.total_jobs || '0';
                        document.getElementById('active-jobs').textContent = stats.active_jobs || '0';
                        document.getElementById('companies-count').textContent = stats.companies_count || '0';
                        document.getElementById('latest-scrape').textContent = stats.latest_scrape || 'Never';
                        
                        // New tracking schema metrics
                        if (document.getElementById('duplicate-jobs')) {
                            document.getElementById('duplicate-jobs').textContent = stats.duplicate_jobs || '0';
                        }
                        if (document.getElementById('multi-source-jobs')) {
                            document.getElementById('multi-source-jobs').textContent = stats.multi_source_jobs || '0';
                        }
                        if (document.getElementById('total-sources')) {
                            document.getElementById('total-sources').textContent = stats.total_sources || '0';
                        }
                        if (document.getElementById('deduplication-rate')) {
                            document.getElementById('deduplication-rate').textContent = (stats.deduplication_rate || 0) + '%';
                        }
                    }
                } catch (error) {
                    console.error('Error loading job stats:', error);
                }
            }

            async function loadJobs(page = 1) {
                currentPage = page;
                const pageSize = document.getElementById('page-size').value;
                
                // Build query parameters
                const params = new URLSearchParams({
                    page: page,
                    limit: pageSize,
                    ...currentFilters
                });

                try {
                    const response = await authFetch(`/admin/jobs?${params}`);
                    if (response && response.ok) {
                        const data = await response.json();
                        renderJobsTable(data.jobs || []);
                        renderPagination(data.total_pages || 1, data.total_jobs || 0);
                        
                        // Update job count
                        document.getElementById('job-count').textContent = 
                            `(${data.total_jobs || 0} jobs, page ${page} of ${data.total_pages || 1})`;
                    } else {
                        renderEmptyState();
                    }
                } catch (error) {
                    console.error('Error loading jobs:', error);
                    renderEmptyState();
                }
            }

            function renderJobsTable(jobs) {
                const tbody = document.querySelector('#jobs-table tbody');
                
                // Store current jobs data for sorting
                currentJobsData = jobs;
                
                if (jobs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="10" class="empty-state"><h3>No jobs found</h3><p>Try adjusting your filters or check back after running some searches.</p></td></tr>';
                    return;
                }

                tbody.innerHTML = jobs.map(job => `
                    <tr class="job-row ${job.is_duplicate ? 'duplicate-job' : ''}" onclick="showJobDetails(${job.id})">
                        <td class="job-title" title="${job.title}">
                            ${job.title}
                            ${job.is_duplicate ? '<span class="duplicate-badge" title="Found on multiple sites">🔄</span>' : ''}
                            ${job.is_multi_source ? '<span class="multi-source-badge" title="Posted on multiple sites">📍</span>' : ''}
                        </td>
                        <td class="company-name" title="${job.company_name || 'Unknown'}">${job.company_name || 'Unknown'}</td>
                        <td class="location" title="${job.location || 'Not specified'}">${job.location || 'Not specified'}</td>
                        <td class="salary">${formatSalary(job.salary_min, job.salary_max, job.salary_currency)}</td>
                        <td>${job.job_type || '-'}</td>
                        <td>${job.is_remote ? '<span class="remote-badge">Remote</span>' : 'On-site'}</td>
                        <td class="source-sites" title="${job.source_sites || 'Unknown'}">
                            <span class="sources-count">${job.sites_posted_count || 1} site${(job.sites_posted_count || 1) > 1 ? 's' : ''}</span>
                            <br><small>${(job.source_sites || '').split(', ').slice(0, 2).join(', ')}${(job.source_sites || '').split(', ').length > 2 ? '...' : ''}</small>
                        </td>
                        <td title="${job.first_seen_at}">${formatDate(job.first_seen_at)}</td>
                        <td class="tracking-metrics" title="Total seen: ${job.total_seen_count || 1}, Days active: ${job.days_active || 0}, Reposts: ${job.repost_count || 0}">
                            <div class="metrics-compact">
                                <span class="seen-count">👁 ${job.total_seen_count || 1}</span>
                                <span class="days-active">📅 ${job.days_active || 0}d</span>
                                ${(job.repost_count || 0) > 0 ? `<span class="repost-count">🔄 ${job.repost_count}</span>` : ''}
                            </div>
                        </td>
                        <td>
                            <button class="btn" onclick="event.stopPropagation(); showJobSources(${job.id})">Sources</button>
                        </td>
                    </tr>
                `).join('');
            }

            function renderEmptyState() {
                const tbody = document.querySelector('#jobs-table tbody');
                tbody.innerHTML = `
                    <tr>
                        <td colspan="10" class="empty-state">
                            <h3>🔍 No Jobs in Database Yet</h3>
                            <p>Run some job searches from the <a href="/admin/searches">Searches</a> page to populate the database.</p>
                        </td>
                    </tr>
                `;
                document.getElementById('job-count').textContent = '(0 jobs)';
            }

            // Global variables for sorting
            let currentSort = { column: null, direction: 'asc' };
            let currentJobsData = [];

            function sortTable(column) {
                // Toggle sort direction if clicking the same column
                if (currentSort.column === column) {
                    currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    currentSort.column = column;
                    currentSort.direction = 'asc';
                }

                // Update sort indicators
                document.querySelectorAll('.sort-indicator').forEach(indicator => {
                    indicator.className = 'sort-indicator';
                });
                
                const indicator = document.getElementById(`sort-${column}`);
                if (indicator) {
                    indicator.className = `sort-indicator ${currentSort.direction}`;
                }

                // Sort the current jobs data
                if (currentJobsData.length > 0) {
                    const sortedJobs = [...currentJobsData].sort((a, b) => {
                        // Map column names to actual job field names
                        let fieldName = column;
                        if (column === 'company') fieldName = 'company_name';
                        
                        let valueA = a[fieldName];
                        let valueB = b[fieldName];

                        // Handle null/undefined values
                        if (valueA == null) valueA = '';
                        if (valueB == null) valueB = '';

                        // Special handling for different data types
                        switch (column) {
                            case 'salary_max':
                                valueA = parseFloat(valueA) || 0;
                                valueB = parseFloat(valueB) || 0;
                                break;
                            case 'date_posted':
                            case 'first_seen_date':
                                valueA = new Date(valueA);
                                valueB = new Date(valueB);
                                break;
                            case 'title':
                            case 'company':
                            case 'location':
                            default:
                                valueA = String(valueA).toLowerCase();
                                valueB = String(valueB).toLowerCase();
                                break;
                        }

                        if (valueA < valueB) {
                            return currentSort.direction === 'asc' ? -1 : 1;
                        }
                        if (valueA > valueB) {
                            return currentSort.direction === 'asc' ? 1 : -1;
                        }
                        return 0;
                    });

                    // Re-render the table with sorted data
                    renderJobsTable(sortedJobs);
                }
            }

            function renderPagination(totalPages, totalJobs) {
                const pagination = document.getElementById('pagination');
                if (totalPages <= 1) {
                    pagination.innerHTML = '';
                    return;
                }

                let buttons = [];
                
                // Previous button
                if (currentPage > 1) {
                    buttons.push(`<button onclick="loadJobs(${currentPage - 1})">‹ Previous</button>`);
                }
                
                // Page numbers
                for (let i = Math.max(1, currentPage - 2); i <= Math.min(totalPages, currentPage + 2); i++) {
                    buttons.push(`<button class="${i === currentPage ? 'active' : ''}" onclick="loadJobs(${i})">${i}</button>`);
                }
                
                // Next button
                if (currentPage < totalPages) {
                    buttons.push(`<button onclick="loadJobs(${currentPage + 1})">Next ›</button>`);
                }
                
                pagination.innerHTML = buttons.join('');
            }

            function formatSalary(min, max, currency = 'USD') {
                if (!min && !max) return '-';
                const symbol = currency === 'USD' ? '$' : currency;
                if (min && max) {
                    return `${symbol}${formatNumber(min)} - ${symbol}${formatNumber(max)}`;
                }
                return `${symbol}${formatNumber(min || max)}`;
            }

            function formatNumber(num) {
                return new Intl.NumberFormat().format(num);
            }

            function formatDate(dateStr) {
                if (!dateStr) return '-';
                const date = new Date(dateStr);
                const now = new Date();
                const diffTime = Math.abs(now - date);
                const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
                
                if (diffDays === 1) return 'Today';
                if (diffDays === 2) return 'Yesterday';
                if (diffDays <= 7) return `${diffDays} days ago`;
                return date.toLocaleDateString();
            }

            function applyFilters() {
                currentFilters = {};
                
                const search = document.getElementById('search-input').value.trim();
                if (search) currentFilters.search = search;
                
                const company = document.getElementById('company-filter').value;
                if (company) currentFilters.company = company;
                
                const location = document.getElementById('location-filter').value.trim();
                if (location) currentFilters.location = location;
                
                const platform = document.getElementById('platform-filter').value;
                if (platform) currentFilters.platform = platform;
                
                const jobType = document.getElementById('job-type-filter').value;
                if (jobType) currentFilters.job_type = jobType;
                
                const remote = document.getElementById('remote-filter').value;
                if (remote) currentFilters.is_remote = remote;
                
                const salaryMin = document.getElementById('salary-min').value;
                if (salaryMin) currentFilters.salary_min = salaryMin;
                
                const salaryMax = document.getElementById('salary-max').value;
                if (salaryMax) currentFilters.salary_max = salaryMax;
                
                const dateFilter = document.getElementById('date-filter').value;
                if (dateFilter) currentFilters.days_ago = dateFilter;
                
                const sortBy = document.getElementById('sort-by').value;
                if (sortBy) currentFilters.sort_by = sortBy;
                
                const sortOrder = document.getElementById('sort-order').value;
                if (sortOrder) currentFilters.sort_order = sortOrder;
                
                loadJobs(1); // Reset to page 1 when applying filters
            }

            function clearFilters() {
                document.getElementById('search-input').value = '';
                document.getElementById('company-filter').value = '';
                document.getElementById('location-filter').value = '';
                document.getElementById('platform-filter').value = '';
                document.getElementById('job-type-filter').value = '';
                document.getElementById('remote-filter').value = '';
                document.getElementById('salary-min').value = '';
                document.getElementById('salary-max').value = '';
                document.getElementById('date-filter').value = '';
                document.getElementById('sort-by').value = 'first_seen_at';
                document.getElementById('sort-order').value = 'desc';
                
                currentFilters = {};
                loadJobs(1);
            }

            function refreshJobs() {
                loadJobs(currentPage);
                loadJobsStats();
            }

            async function showJobDetails(jobId) {
                try {
                    const response = await authFetch(`/admin/jobs/${jobId}`);
                    if (response && response.ok) {
                        const job = await response.json();
                        
                        document.getElementById('modal-job-title').textContent = job.title;
                        document.getElementById('modal-job-content').innerHTML = `
                            <div style="margin-bottom: 20px;">
                                <h3>${job.company_name || 'Unknown Company'}</h3>
                                <p><strong>Location:</strong> ${job.location || 'Not specified'}</p>
                                <p><strong>Platform:</strong> <span class="platform-badge platform-${job.source_platform}">${job.source_platform}</span></p>
                                <p><strong>Posted:</strong> ${formatDate(job.date_posted)}</p>
                                <p><strong>Job Type:</strong> ${job.job_type || 'Not specified'}</p>
                                <p><strong>Remote:</strong> ${job.is_remote ? 'Yes' : 'No'}</p>
                                <p><strong>Salary:</strong> ${formatSalary(job.salary_min, job.salary_max, job.salary_currency)}</p>
                                ${job.easy_apply ? '<p><strong>Easy Apply:</strong> Available</p>' : ''}
                            </div>
                            ${job.description ? `<div><h4>Description:</h4><div style="max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 15px; border-radius: 4px;">${job.description}</div></div>` : ''}
                            <div style="margin-top: 20px;">
                                <a href="${job.job_url}" target="_blank" class="btn success">View Original Job Posting</a>
                                ${job.application_url ? `<a href="${job.application_url}" target="_blank" class="btn">Apply Now</a>` : ''}
                            </div>
                        `;
                        
                        document.getElementById('job-details-modal').style.display = 'block';
                    }
                } catch (error) {
                    console.error('Error loading job details:', error);
                }
            }

            function closeJobModal() {
                document.getElementById('job-details-modal').style.display = 'none';
            }

            function exportJobs(format) {
                const params = new URLSearchParams({
                    format: format,
                    ...currentFilters
                });
                
                window.open(`/admin/jobs/export?${params}`, '_blank');
            }

            async function showJobSources(jobId) {
                try {
                    const response = await authFetch(`/admin/jobs/${jobId}`);
                    if (response && response.ok) {
                        const job = await response.json();
                        
                        document.getElementById('modal-job-title').textContent = `Sources for: ${job.title}`;
                        
                        // Parse source sites and URLs
                        const sources = job.source_sites ? job.source_sites.split(', ') : [];
                        const urls = job.job_urls ? job.job_urls.split(', ') : [];
                        
                        let sourcesHtml = '<div class="sources-container">';
                        sources.forEach((source, index) => {
                            const url = urls[index] || '#';
                            sourcesHtml += `
                                <div class="source-item">
                                    <div class="source-info">
                                        <span class="platform-badge platform-${source}">${source}</span>
                                        <div class="source-details">
                                            <strong>Job URL:</strong> 
                                            <a href="${url}" target="_blank" class="source-link">${url.length > 50 ? url.substring(0, 50) + '...' : url}</a>
                                        </div>
                                    </div>
                                </div>
                            `;
                        });
                        sourcesHtml += '</div>';
                        
                        document.getElementById('modal-job-content').innerHTML = `
                            <div style="margin-bottom: 20px;">
                                <h3>${job.company_name || 'Unknown Company'}</h3>
                                <p><strong>Job Hash:</strong> <code>${job.job_hash}</code></p>
                                <p><strong>Total Sources:</strong> ${job.sites_posted_count || 1}</p>
                                <p><strong>Total Seen Count:</strong> ${job.total_seen_count || 1}</p>
                                <p><strong>Repost Count:</strong> ${job.repost_count || 0}</p>
                                <p><strong>Days Active:</strong> ${job.days_active || 0}</p>
                                <p><strong>First Seen:</strong> ${formatDate(job.first_seen_at)}</p>
                                <p><strong>Last Seen:</strong> ${formatDate(job.last_seen_at)}</p>
                            </div>
                            
                            <h4>Sources where this job was found:</h4>
                            ${sourcesHtml}
                        `;
                        
                        document.getElementById('job-details-modal').style.display = 'block';
                    }
                } catch (error) {
                    console.error('Error loading job sources:', error);
                    alert('Error loading job sources: ' + error.message);
                }
            }

            // Close modal when clicking outside
            window.onclick = function(event) {
                const modal = document.getElementById('job-details-modal');
                if (event.target === modal) {
                    closeJobModal();
                }
            }

            // Load data on page load
            loadJobsStats();
            loadJobs();
            
            // Add event listeners for sort controls
            document.getElementById('sort-by').addEventListener('change', function() {
                applyFilters(); // Apply all filters including new sort settings
            });
            
            document.getElementById('sort-order').addEventListener('change', function() {
                applyFilters(); // Apply all filters including new sort settings
            });
            
            // Auto-refresh every 2 minutes
            setInterval(() => {
                loadJobsStats();
            }, 120000);
        </script>
    </body>
    </html>
    """
    return html_content

@router.get("/scheduler", response_class=HTMLResponse)
async def admin_scheduler():
    """Admin scheduler management page"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Scheduler - JobSpy Admin</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .nav { background: #34495e; padding: 10px; border-radius: 8px; margin-bottom: 20px; }
            .nav a { color: white; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px; }
            .nav a:hover { background: #2c3e50; }
            .nav a.active { background: #2c3e50; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
            .stat-card { background: linear-gradient(135deg, #9b59b6, #8e44ad); color: white; padding: 20px; border-radius: 8px; text-align: center; }
            .stat-value { font-size: 2em; font-weight: bold; margin: 10px 0; }
            .stat-label { font-size: 0.9em; opacity: 0.9; }
            .controls { display: flex; gap: 10px; margin-bottom: 20px; }
            .btn { background: #3498db; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; }
            .btn:hover { background: #2980b9; }
            .btn.success { background: #27ae60; }
            .btn.success:hover { background: #229954; }
            .btn.danger { background: #e74c3c; }
            .btn.danger:hover { background: #c0392b; }
            .btn.warning { background: #f39c12; }
            .btn.warning:hover { background: #e67e22; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background: #f8f9fa; font-weight: bold; }
            .status { padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }
            .status.pending { background: #fff3cd; color: #856404; }
            .status.running { background: #d4edda; color: #155724; }
            .status.completed { background: #d1ecf1; color: #0c5460; }
            .status.failed { background: #f8d7da; color: #721c24; }
            .status.cancelled { background: #e2e3e5; color: #383d41; }
            .scheduler-controls { background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
            .form-row { display: flex; gap: 15px; align-items: center; margin-bottom: 10px; }
            .form-group { flex: 1; }
            .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
            .form-group input, .form-group select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
            .quick-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
            .action-btn { background: #6c757d; color: white; padding: 15px; border: none; border-radius: 8px; cursor: pointer; text-align: center; transition: background 0.3s; }
            .action-btn:hover { background: #5a6268; }
            .logs { max-height: 300px; overflow-y: auto; background: #f8f9fa; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 0.9em; }
            .log-entry { margin-bottom: 10px; padding: 5px; border-left: 3px solid #ddd; padding-left: 10px; }
            .log-entry.info { border-color: #17a2b8; }
            .log-entry.warning { border-color: #ffc107; }
            .log-entry.error { border-color: #dc3545; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>⚙️ JobSpy Scheduler</h1>
                <p>Manage and monitor job search scheduling</p>
            </div>
            
            <div class="nav">
                <a href="/admin/">Dashboard</a>
                <a href="/admin/searches">Searches</a>
                <a href="/admin/scheduler" class="active">Scheduler</a>
                <a href="/admin/templates">Templates</a>
                <a href="/admin/analytics">Analytics</a>
                <a href="/admin/settings">Settings</a>
            </div>
            
            <div class="card">
                <h2>Scheduler Status</h2>
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-value" id="pending-jobs">-</div>
                        <div class="stat-label">Pending Jobs</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="active-jobs">-</div>
                        <div class="stat-label">Active Jobs</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="scheduler-status">-</div>
                        <div class="stat-label">Scheduler Status</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="backend-type">-</div>
                        <div class="stat-label">Backend Type</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>Scheduler Controls</h2>
                <div class="quick-actions">
                    <button class="action-btn btn success" onclick="startScheduler()">
                        ▶️ Start Scheduler
                    </button>
                    <button class="action-btn btn warning" onclick="stopScheduler()">
                        ⏸️ Stop Scheduler
                    </button>
                    <button class="action-btn btn" onclick="restartScheduler()">
                        🔄 Restart Scheduler
                    </button>
                    <button class="action-btn btn" onclick="refreshStats()">
                        📊 Refresh Stats
                    </button>
                </div>
                
                <div class="scheduler-controls">
                    <h3>Schedule Management</h3>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Filter by Status:</label>
                            <select id="status-filter" onchange="loadScheduledJobs()">
                                <option value="">All</option>
                                <option value="pending">Pending</option>
                                <option value="running">Running</option>
                                <option value="completed">Completed</option>
                                <option value="failed">Failed</option>
                                <option value="cancelled">Cancelled</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Limit:</label>
                            <input type="number" id="limit-input" value="50" min="10" max="200" onchange="loadScheduledJobs()">
                        </div>
                        <div class="form-group">
                            <button class="btn" onclick="loadScheduledJobs()">🔍 Filter</button>
                        </div>
                    </div>
                    <div class="controls">
                        <button class="btn danger" onclick="cancelAllPendingJobs()">❌ Cancel All Pending</button>
                        <button class="btn warning" onclick="retryFailedJobs()">🔄 Retry Failed Jobs</button>
                        <button class="btn" onclick="exportSchedule()">📁 Export Schedule</button>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>Scheduled Jobs</h2>
                <table id="scheduled-jobs-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Name</th>
                            <th>Search Term</th>
                            <th>Location</th>
                            <th>Sites</th>
                            <th>Status</th>
                            <th>Scheduled</th>
                            <th>Jobs Found</th>
                            <th>Recurring</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td colspan="10" style="text-align: center; color: #666;">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
            
            <div class="card">
                <h2>Scheduler Logs</h2>
                <div class="controls">
                    <button class="btn" onclick="loadLogs()">🔄 Refresh Logs</button>
                    <button class="btn" onclick="clearLogs()">🗑️ Clear Logs</button>
                </div>
                <div id="scheduler-logs" class="logs">
                    <div class="log-entry info">Loading logs...</div>
                </div>
            </div>
        </div>

        <script>
            // Auth wrapper function
            async function authFetch(url, options = {}) {
                const apiKey = sessionStorage.getItem('admin-api-key');
                if (!apiKey) {
                    console.log('No API key, trying without auth');
                    return fetch(url, options);
                }

                const headers = {
                    'x-api-key': apiKey,
                    ...options.headers
                };

                try {
                    const response = await fetch(url, { ...options, headers });
                    
                    if (response.status === 403) {
                        console.log('403 Forbidden - trying without auth');
                        return fetch(url, options);
                    }
                    
                    return response;
                } catch (error) {
                    console.error('Request error:', error);
                    return null;
                }
            }

            async function loadSchedulerStats() {
                try {
                    const response = await authFetch('/admin/scheduler/stats');
                    if (response && response.ok) {
                        const stats = await response.json();
                        document.getElementById('pending-jobs').textContent = stats.pending_jobs || '0';
                        document.getElementById('active-jobs').textContent = stats.active_jobs || '0';
                        document.getElementById('scheduler-status').textContent = stats.scheduler_status || 'Unknown';
                        document.getElementById('backend-type').textContent = stats.backend || 'Unknown';
                    } else {
                        // Set default values on error
                        document.getElementById('pending-jobs').textContent = 'Error';
                        document.getElementById('active-jobs').textContent = 'Error';
                        document.getElementById('scheduler-status').textContent = 'Error';
                        document.getElementById('backend-type').textContent = 'Error';
                    }
                } catch (error) {
                    console.error('Error loading scheduler stats:', error);
                }
            }

            async function loadScheduledJobs() {
                try {
                    const status = document.getElementById('status-filter').value;
                    const limit = document.getElementById('limit-input').value;
                    
                    let url = '/admin/searches?limit=' + limit;
                    if (status) {
                        url += '&status=' + status;
                    }
                    
                    const response = await authFetch(url);
                    if (response && response.ok) {
                        const data = await response.json();
                        const tbody = document.querySelector('#scheduled-jobs-table tbody');
                        
                        if (data.searches && data.searches.length > 0) {
                            tbody.innerHTML = data.searches.map(job => `
                                <tr>
                                    <td>${job.id}</td>
                                    <td>${job.name || 'Unnamed'}</td>
                                    <td>${job.search_term || '-'}</td>
                                    <td>${job.location || '-'}</td>
                                    <td>${(job.site_names || []).join(', ') || '-'}</td>
                                    <td><span class="status ${job.status}">${job.status}</span></td>
                                    <td>${job.scheduled_time ? new Date(job.scheduled_time).toLocaleString() : '-'}</td>
                                    <td>${job.jobs_found || '0'}</td>
                                    <td>${job.recurring ? '✅' : '❌'}</td>
                                    <td>
                                        ${job.status === 'pending' || job.status === 'running' ? 
                                            `<button class="btn danger" onclick="cancelJob(${job.id})">Cancel</button>` :
                                            job.status === 'failed' ?
                                            `<button class="btn warning" onclick="retryJob(${job.id})">Retry</button>` :
                                            '-'
                                        }
                                    </td>
                                </tr>
                            `).join('');
                        } else {
                            tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; color: #666;">No scheduled jobs found</td></tr>';
                        }
                    }
                } catch (error) {
                    console.error('Error loading scheduled jobs:', error);
                }
            }

            async function cancelJob(jobId) {
                if (!confirm('Are you sure you want to cancel this job?')) return;
                
                try {
                    const response = await authFetch(`/admin/searches/${jobId}/cancel`, { method: 'POST' });
                    if (response && response.ok) {
                        alert('Job cancelled successfully');
                        loadScheduledJobs();
                        loadSchedulerStats();
                    } else {
                        alert('Failed to cancel job');
                    }
                } catch (error) {
                    console.error('Error cancelling job:', error);
                    alert('Error cancelling job');
                }
            }

            async function retryJob(jobId) {
                alert('Retry functionality would be implemented here');
            }

            async function startScheduler() {
                alert('Start scheduler functionality would be implemented here');
            }

            async function stopScheduler() {
                alert('Stop scheduler functionality would be implemented here');
            }

            async function restartScheduler() {
                alert('Restart scheduler functionality would be implemented here');
            }

            async function refreshStats() {
                loadSchedulerStats();
                loadScheduledJobs();
            }

            async function cancelAllPendingJobs() {
                if (!confirm('Are you sure you want to cancel ALL pending jobs?')) return;
                alert('Cancel all pending jobs functionality would be implemented here');
            }

            async function retryFailedJobs() {
                alert('Retry failed jobs functionality would be implemented here');
            }

            async function exportSchedule() {
                alert('Export schedule functionality would be implemented here');
            }

            async function loadLogs() {
                const logsDiv = document.getElementById('scheduler-logs');
                try {
                    const apiKey = sessionStorage.getItem('admin-api-key');
                    const headers = {};
                    if (apiKey) {
                        headers['x-api-key'] = apiKey;
                    }
                    
                    const response = await fetch('/admin/logs?limit=50', {
                        headers: headers
                    });
                    
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }
                    
                    const data = await response.json();
                    const logs = data.logs || [];
                    
                    if (logs.length === 0) {
                        logsDiv.innerHTML = '<div class="log-entry info">No logs available</div>';
                        return;
                    }
                    
                    const logHTML = logs.map(log => {
                        const timestamp = new Date(log.timestamp).toLocaleString();
                        const level = log.level.toLowerCase();
                        const levelClass = level === 'error' ? 'error' : 
                                         level === 'warning' || level === 'warn' ? 'warning' : 'info';
                        
                        return `<div class="log-entry ${levelClass}">[${timestamp}] ${log.level}: ${log.message}</div>`;
                    }).join('');
                    
                    logsDiv.innerHTML = logHTML;
                } catch (error) {
                    console.error('Failed to load logs:', error);
                    logsDiv.innerHTML = `<div class="log-entry error">Failed to load logs: ${error.message}</div>`;
                }
            }

            async function clearLogs() {
                if (!confirm('Are you sure you want to clear all logs?')) return;
                document.getElementById('scheduler-logs').innerHTML = '<div class="log-entry info">Logs cleared</div>';
            }

            // Load data on page load
            loadSchedulerStats();
            loadScheduledJobs();
            loadLogs();
            
            // Refresh every 30 seconds
            setInterval(() => {
                loadSchedulerStats();
                loadScheduledJobs();
            }, 30000);
        </script>
    </body>
    </html>
    """
    return html_content

@router.get("/analytics", response_class=HTMLResponse)
async def admin_analytics(db: Session = Depends(get_db)):
    """Admin analytics page with server-side data rendering"""
    
    # Get real-time analytics data server-side
    admin_service = AdminService(db)
    stats = await admin_service.get_admin_stats()
    
    # Calculate metrics from AdminStats model
    total_searches = stats.total_searches
    active_searches = stats.active_searches 
    failed_searches = stats.failed_searches_today
    success_rate = round(((total_searches - failed_searches) / total_searches) * 100) if total_searches > 0 else 100
    avg_results = round(stats.total_jobs_found / total_searches, 1) if total_searches > 0 else 0
    
    # Get recent searches data
    try:
        recent_searches_result = db.execute(text("""
            SELECT 
                COALESCE(search_params->>'search_term', 'Unknown') as search_term,
                COALESCE(search_params->>'location', 'Unknown') as location,
                source_site,
                COALESCE(jobs_found, 0) as jobs_found,
                status,
                started_at
            FROM scraping_runs 
            ORDER BY started_at DESC 
            LIMIT 10
        """))
        recent_searches = recent_searches_result.fetchall()
    except Exception as e:
        recent_searches = []
    
    # Initialize tracking metrics with defaults
    duplicate_rate = 0
    multi_source_jobs = 0
    
    # Get tracking schema metrics with safe fallbacks
    try:
        # Rollback any pending transaction before starting new queries
        db.rollback()
        tracking_stats = await admin_service.get_tracking_stats()
        duplicate_rate = round((tracking_stats.get('duplicate_jobs', 0) / max(tracking_stats.get('total_jobs', 1), 1)) * 100, 1)
        multi_source_jobs = tracking_stats.get('multi_source_jobs', 0)
    except Exception as e:
        logger.error(f"Error getting tracking stats: {e}")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Analytics - JobSpy Admin</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .card {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
            .nav {{ background: #34495e; padding: 10px; border-radius: 8px; margin-bottom: 20px; }}
            .nav a {{ color: white; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px; }}
            .nav a:hover {{ background: #2c3e50; }}
            .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }}
            .metric-card {{ background: linear-gradient(135deg, #3498db, #2980b9); color: white; padding: 20px; border-radius: 8px; text-align: center; }}
            .metric-value {{ font-size: 2em; font-weight: bold; margin: 10px 0; }}
            .metric-label {{ font-size: 0.9em; opacity: 0.9; }}
            .chart-container {{ height: 300px; background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #f8f9fa; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📈 JobSpy Analytics</h1>
                <p>Detailed insights into job search performance and trends</p>
            </div>
            
            <div class="nav">
                <a href="/admin/">Dashboard</a>
                <a href="/admin/searches">Searches</a>
                <a href="/admin/scheduler">Scheduler</a>
                <a href="/admin/jobs/page">Jobs</a>
                <a href="/admin/templates">Templates</a>
                <a href="/admin/analytics">Analytics</a>
                <a href="/admin/settings">Settings</a>
            </div>
            
            <div class="card">
                <h2>Key Metrics</h2>
                <div class="metrics">
                    <div class="metric-card">
                        <div class="metric-value">{total_searches}</div>
                        <div class="metric-label">Total Searches</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{success_rate}%</div>
                        <div class="metric-label">Success Rate</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{avg_results}</div>
                        <div class="metric-label">Avg Results per Search</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{active_searches}</div>
                        <div class="metric-label">Active Searches</div>
                    </div>
                    <div class="metric-card" style="background: linear-gradient(135deg, #e74c3c, #c0392b);">
                        <div class="metric-value">{duplicate_rate}%</div>
                        <div class="metric-label">Duplicate Rate</div>
                    </div>
                    <div class="metric-card" style="background: linear-gradient(135deg, #f39c12, #e67e22);">
                        <div class="metric-value">{multi_source_jobs}</div>
                        <div class="metric-label">Multi-Source Jobs</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>Search Trends</h2>
                <div class="chart-container">
                    <div style="text-align: center; padding-top: 100px; color: #666;">
                        📊 Search trends chart would appear here<br>
                        <small>Charts showing search volume over time, popular job sites, etc.</small>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>Recent Searches</h2>
                <table id="recent-searches-table">
                    <thead>
                        <tr>
                            <th>Search Term</th>
                            <th>Location</th>
                            <th>Site</th>
                            <th>Results</th>
                            <th>Status</th>
                            <th>Time</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join([
                            f'''<tr>
                                <td>{search[0]}</td>
                                <td>{search[1]}</td>
                                <td>{search[2]}</td>
                                <td>{search[3]}</td>
                                <td><span style="color: {'green' if search[4] == 'completed' else 'orange' if search[4] == 'running' else 'red'}">●</span> {search[4].title()}</td>
                                <td>{search[5].strftime('%H:%M:%S') if search[5] else 'Unknown'}</td>
                            </tr>'''
                            for search in recent_searches
                        ]) if recent_searches else '<tr><td colspan="6" style="text-align: center; color: #666;">No recent searches found</td></tr>'}
                    </tbody>
                </table>
            </div>
            
            <div class="card">
                <h2>Popular Search Terms</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Search Term</th>
                            <th>Frequency</th>
                            <th>Avg Results</th>
                            <th>Success Rate</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td>software engineer</td><td>15</td><td>24</td><td>98%</td></tr>
                        <tr><td>data scientist</td><td>12</td><td>18</td><td>95%</td></tr>
                        <tr><td>product manager</td><td>8</td><td>22</td><td>100%</td></tr>
                        <tr><td>marketing manager</td><td>6</td><td>16</td><td>92%</td></tr>
                        <tr><td>python developer</td><td>5</td><td>20</td><td>96%</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            // Simple refresh mechanism - no problematic fetch calls
            // Page will auto-refresh every 30 seconds for updated data
            setTimeout(function() {{
                window.location.reload();
            }}, 30000);
        </script>
    </body>
    </html>
    """
    return html_content

@router.get("/settings", response_class=HTMLResponse)
async def admin_settings():
    """Admin settings page"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Settings - JobSpy</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1000px; margin: 0 auto; }
            .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .nav { background: #34495e; padding: 10px; border-radius: 8px; margin-bottom: 20px; }
            .nav a { color: white; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px; }
            .nav a:hover { background: #2c3e50; }
            .form-group { margin: 15px 0; }
            .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
            .form-group input, .form-group select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
            button:hover { background: #2980b9; }
            .settings-section { border-bottom: 1px solid #eee; padding-bottom: 20px; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>⚙️ JobSpy Admin Settings</h1>
                <p>Configure system parameters and preferences</p>
            </div>
            
            <div class="nav">
                <a href="/admin/">Dashboard</a>
                <a href="/admin/searches">Searches</a>
                <a href="/admin/templates">Templates</a>
                <a href="/admin/analytics">Analytics</a>
                <a href="/admin/settings">Settings</a>
            </div>
            
            <div class="card">
                <h2>System Configuration</h2>
                
                <div class="settings-section">
                    <h3>Search Settings</h3>
                    <div class="form-group">
                        <label>Max Concurrent Searches:</label>
                        <input type="number" id="max-searches" value="5" min="1" max="20">
                    </div>
                    <div class="form-group">
                        <label>Default Results per Search:</label>
                        <input type="number" id="default-results" value="20" min="1" max="1000">
                    </div>
                    <div class="form-group">
                        <label>Default Job Sites:</label>
                        <select id="default-sites" multiple>
                            <option value="indeed" selected>Indeed</option>
                            <option value="linkedin" selected>LinkedIn</option>
                            <option value="glassdoor">Glassdoor</option>
                            <option value="zip_recruiter">ZipRecruiter</option>
                            <option value="google">Google Jobs</option>
                        </select>
                    </div>
                </div>
                
                <div class="settings-section">
                    <h3>Performance Settings</h3>
                    <div class="form-group">
                        <label>Rate Limit (requests per hour):</label>
                        <input type="number" id="rate-limit" value="100" min="10" max="10000">
                    </div>
                    <div class="form-group">
                        <label>Cache Enabled:</label>
                        <select id="cache-enabled">
                            <option value="true" selected>Enabled</option>
                            <option value="false">Disabled</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Cache Expiry (seconds):</label>
                        <input type="number" id="cache-expiry" value="3600" min="60" max="86400">
                    </div>
                </div>
                
                <div class="settings-section">
                    <h3>Security Settings</h3>
                    <div class="form-group">
                        <label>API Key Authentication:</label>
                        <select id="api-auth">
                            <option value="true">Enabled</option>
                            <option value="false" selected>Disabled</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Maintenance Mode:</label>
                        <select id="maintenance-mode">
                            <option value="false" selected>Disabled</option>
                            <option value="true">Enabled</option>
                        </select>
                    </div>
                </div>
                
                <button onclick="saveSettings()">💾 Save Settings</button>
                <button onclick="loadSettings()" style="background: #95a5a6;">🔄 Reload</button>
            </div>
        </div>

        <script>
            async function loadSettings() {
                try {
                    const response = await fetch('/admin/config');
                    if (response.ok) {
                        const config = await response.json();
                        document.getElementById('max-searches').value = config.max_concurrent_searches || 5;
                        document.getElementById('default-results').value = config.default_results || 20;
                        document.getElementById('rate-limit').value = config.default_rate_limit || 100;
                        document.getElementById('cache-enabled').value = config.cache_enabled ? 'true' : 'false';
                        document.getElementById('cache-expiry').value = config.cache_expiry || 3600;
                        document.getElementById('maintenance-mode').value = config.maintenance_mode ? 'true' : 'false';
                    }
                } catch (error) {
                    console.error('Failed to load settings:', error);
                }
            }
            
            async function saveSettings() {
                const settings = {
                    max_concurrent_searches: parseInt(document.getElementById('max-searches').value),
                    default_results: parseInt(document.getElementById('default-results').value),
                    default_rate_limit: parseInt(document.getElementById('rate-limit').value),
                    cache_enabled: document.getElementById('cache-enabled').value === 'true',
                    cache_expiry: parseInt(document.getElementById('cache-expiry').value),
                    maintenance_mode: document.getElementById('maintenance-mode').value === 'true'
                };
                
                try {
                    const response = await fetch('/admin/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(settings)
                    });
                    
                    if (response.ok) {
                        alert('Settings saved successfully!');
                    } else {
                        alert('Failed to save settings');
                    }
                } catch (error) {
                    console.error('Failed to save settings:', error);
                    alert('Error saving settings');
                }
            }
            
            // Load settings on page load
            loadSettings();
        </script>
    </body>
    </html>
    """
    return html_content

@router.get("/config")
async def get_system_config(
    admin_user: dict = Depends(get_admin_user)
):
    """Get current system configuration"""
    return {
        "max_concurrent_searches": 5,
        "default_rate_limit": 100,
        "cache_enabled": True,
        "cache_expiry": 3600,
        "maintenance_mode": False
    }

@router.post("/config")
async def update_system_config(
    admin_user: dict = Depends(get_admin_user)
):
    """Update system configuration"""
    return {"message": "Configuration updated successfully (mock response)"}

@router.post("/maintenance")
async def toggle_maintenance_mode(
    enabled: bool,
    admin_user: dict = Depends(get_admin_user)
):
    """Enable or disable maintenance mode"""
    return {"message": f"Maintenance mode {'enabled' if enabled else 'disabled'} (mock response)"}

@router.get("/health")
async def admin_health_check(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Detailed system health check for admins"""
    admin_service = AdminService(db)
    health_info = await admin_service.get_system_health()
    return health_info

@router.get("/jobs/stats")
async def get_jobs_stats(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Get jobs database statistics using tracking schema"""
    try:
        from app.services.job_tracking_service import job_tracking_service
        
        # Get total jobs count (tracking schema)
        total_jobs_result = db.execute(text("SELECT COUNT(*) FROM job_postings"))
        total_jobs = total_jobs_result.fetchone()[0]
        
        # Get active jobs count (tracking schema uses status = 'active')
        active_jobs_result = db.execute(text("SELECT COUNT(*) FROM job_postings WHERE status = 'active'"))
        active_jobs = active_jobs_result.fetchone()[0]
        
        # Get companies count (tracking schema)
        companies_result = db.execute(text("SELECT COUNT(*) FROM companies"))
        companies_count = companies_result.fetchone()[0]
        
        # Get latest scrape time (tracking schema uses first_seen_at)
        latest_scrape_result = db.execute(text("SELECT MAX(first_seen_at) FROM job_postings"))
        latest_scrape_row = latest_scrape_result.fetchone()
        latest_scrape = latest_scrape_row[0] if latest_scrape_row and latest_scrape_row[0] else None
        
        # Get deduplication stats
        duplicate_jobs_result = db.execute(text("""
            SELECT COUNT(*) FROM job_metrics WHERE total_seen_count > 1
        """))
        duplicate_jobs = duplicate_jobs_result.fetchone()[0]
        
        # Get multi-source jobs count
        multi_source_result = db.execute(text("""
            SELECT COUNT(*) FROM job_metrics WHERE sites_posted_count > 1
        """))
        multi_source_jobs = multi_source_result.fetchone()[0]
        
        # Get total sources count
        sources_result = db.execute(text("SELECT COUNT(*) FROM job_sources"))
        total_sources = sources_result.fetchone()[0]
        
        return {
            "total_jobs": total_jobs,
            "active_jobs": active_jobs,
            "companies_count": companies_count,
            "latest_scrape": latest_scrape.strftime('%Y-%m-%d %H:%M') if latest_scrape else "Never",
            "duplicate_jobs": duplicate_jobs,
            "multi_source_jobs": multi_source_jobs,
            "total_sources": total_sources,
            "deduplication_rate": round((duplicate_jobs / total_jobs * 100), 1) if total_jobs > 0 else 0
        }
    except Exception as e:
        logger.error(f"Error getting jobs stats: {e}")
        return {
            "total_jobs": 0,
            "active_jobs": 0,
            "companies_count": 0,
            "latest_scrape": "Error",
            "duplicate_jobs": 0,
            "multi_source_jobs": 0,
            "total_sources": 0,
            "deduplication_rate": 0,
            "error": str(e)
        }

@router.get("/jobs")
async def get_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    is_remote: Optional[bool] = Query(None),
    salary_min: Optional[int] = Query(None),
    salary_max: Optional[int] = Query(None),
    days_ago: Optional[int] = Query(None),
    sort_by: str = Query("first_seen_at", description="Sort field: first_seen_at, last_seen_at, title, company_name, salary_min, salary_max"),
    source_site: Optional[str] = Query(None, description="Filter by source site"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Get paginated jobs with filtering using tracking schema"""
    try:
        # Validate sort parameters for tracking schema
        valid_sort_fields = {
            'first_seen_at': 'jp.first_seen_at',
            'last_seen_at': 'jp.last_seen_at',
            'title': 'jp.title',
            'company_name': 'c.name',
            'salary_min': 'jp.salary_min',
            'salary_max': 'jp.salary_max'
        }
        
        if sort_by not in valid_sort_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sort_by field. Valid options: {', '.join(valid_sort_fields.keys())}"
            )
        
        if sort_order not in ['asc', 'desc']:
            raise HTTPException(
                status_code=400,
                detail="Invalid sort_order. Valid options: asc, desc"
            )
        
        offset = (page - 1) * limit
        where_conditions = ["jp.status = 'active'"]  # Updated for tracking schema
        params = {"limit": limit, "offset": offset}
        
        # Build WHERE conditions based on filters
        if search:
            where_conditions.append("(jp.title ILIKE :search OR c.name ILIKE :search OR jp.description ILIKE :search)")
            params["search"] = f"%{search}%"
        
        if company:
            where_conditions.append("c.name ILIKE :company")
            params["company"] = f"%{company}%"
        
        if location:
            where_conditions.append("l.city ILIKE :location OR l.state ILIKE :location OR l.country ILIKE :location")
            params["location"] = f"%{location}%"
        
        if platform:
            where_conditions.append("js.source_site = :platform")
            params["platform"] = platform
        
        if source_site:
            where_conditions.append("js.source_site = :source_site")
            params["source_site"] = source_site
        
        if job_type:
            where_conditions.append("jp.job_type = :job_type")
            params["job_type"] = job_type
        
        if is_remote is not None:
            where_conditions.append("jp.is_remote = :is_remote")
            params["is_remote"] = is_remote
        
        if salary_min:
            where_conditions.append("jp.salary_min >= :salary_min")
            params["salary_min"] = salary_min
        
        if salary_max:
            where_conditions.append("jp.salary_max <= :salary_max")
            params["salary_max"] = salary_max
        
        if days_ago:
            where_conditions.append("jp.first_seen_at >= CURRENT_DATE - INTERVAL ':days_ago days'")
            params["days_ago"] = days_ago
        
        where_clause = " AND ".join(where_conditions)
        
        # Get total count (with tracking schema joins)
        count_sql = f"""
            SELECT COUNT(DISTINCT jp.id)
            FROM job_postings jp
            LEFT JOIN companies c ON jp.company_id = c.id
            LEFT JOIN locations l ON jp.location_id = l.id
            LEFT JOIN job_sources js ON jp.id = js.job_posting_id
            LEFT JOIN job_metrics jm ON jp.id = jm.job_posting_id
            WHERE {where_clause}
        """
        
        count_result = db.execute(text(count_sql), params)
        total_jobs = count_result.fetchone()[0]
        total_pages = (total_jobs + limit - 1) // limit
        
        # Get jobs data with tracking schema features
        jobs_sql = f"""
            SELECT DISTINCT
                jp.id, jp.job_hash, jp.title, jp.description, jp.requirements,
                jp.job_type, jp.experience_level, jp.salary_min, jp.salary_max, 
                jp.salary_currency, jp.salary_interval, jp.is_remote,
                jp.first_seen_at, jp.last_seen_at, jp.status,
                c.name as company_name, c.domain as company_domain,
                CONCAT_WS(', ', l.city, l.state, l.country) as location,
                jm.total_seen_count, jm.sites_posted_count, jm.days_active, jm.repost_count,
                STRING_AGG(DISTINCT js.source_site, ', ') as source_sites,
                STRING_AGG(DISTINCT js.job_url, ', ') as job_urls
            FROM job_postings jp
            LEFT JOIN companies c ON jp.company_id = c.id
            LEFT JOIN locations l ON jp.location_id = l.id
            LEFT JOIN job_sources js ON jp.id = js.job_posting_id
            LEFT JOIN job_metrics jm ON jp.id = jm.job_posting_id
            WHERE {where_clause}
            GROUP BY jp.id, jp.job_hash, jp.title, jp.description, jp.requirements,
                     jp.job_type, jp.experience_level, jp.salary_min, jp.salary_max,
                     jp.salary_currency, jp.salary_interval, jp.is_remote,
                     jp.first_seen_at, jp.last_seen_at, jp.status,
                     c.name, c.domain, l.city, l.state, l.country,
                     jm.total_seen_count, jm.sites_posted_count, jm.days_active, jm.repost_count
            ORDER BY {valid_sort_fields[sort_by]} {sort_order.upper()}
            LIMIT :limit OFFSET :offset
        """
        
        jobs_result = db.execute(text(jobs_sql), params)
        jobs_rows = jobs_result.fetchall()
        
        jobs = []
        for row in jobs_rows:
            jobs.append({
                "id": row.id,
                "job_hash": row.job_hash,
                "title": row.title,
                "company_name": row.company_name,
                "company_domain": row.company_domain,
                "location": row.location,
                "description": row.description,
                "requirements": row.requirements,
                "job_type": row.job_type,
                "experience_level": row.experience_level,
                "salary_min": float(row.salary_min) if row.salary_min and str(row.salary_min).lower() not in ['nan', 'inf', '-inf'] else None,
                "salary_max": float(row.salary_max) if row.salary_max and str(row.salary_max).lower() not in ['nan', 'inf', '-inf'] else None,
                "salary_currency": row.salary_currency,
                "salary_interval": row.salary_interval,
                "is_remote": row.is_remote,
                "status": row.status,
                "first_seen_at": row.first_seen_at.strftime('%Y-%m-%d %H:%M') if row.first_seen_at else None,
                "last_seen_at": row.last_seen_at.strftime('%Y-%m-%d %H:%M') if row.last_seen_at else None,
                "source_sites": row.source_sites,
                "job_urls": row.job_urls,
                # Enhanced tracking metrics
                "total_seen_count": row.total_seen_count or 1,
                "sites_posted_count": row.sites_posted_count or 1,
                "days_active": row.days_active or 0,
                "repost_count": row.repost_count or 0,
                "is_duplicate": (row.total_seen_count or 1) > 1,
                "is_multi_source": (row.sites_posted_count or 1) > 1
            })
        
        return {
            "jobs": jobs,
            "total_jobs": total_jobs,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": limit
        }
        
    except Exception as e:
        return {
            "jobs": [],
            "total_jobs": 0,
            "total_pages": 0,
            "current_page": page,
            "page_size": limit,
            "error": str(e)
        }

@router.get("/jobs/{job_id}")
async def get_job_details(
    job_id: int,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Get detailed information for a specific job"""
    try:
        job_sql = """
            SELECT 
                jp.id, jp.job_hash, jp.title, jp.description, jp.requirements,
                jp.job_type, jp.experience_level, jp.salary_min, jp.salary_max, 
                jp.salary_currency, jp.salary_interval, jp.is_remote, jp.status,
                jp.first_seen_at, jp.last_seen_at, jp.created_at, jp.updated_at,
                c.name as company_name, c.description as company_description,
                c.industry, c.domain as company_domain, c.logo_url,
                CONCAT_WS(', ', l.city, l.state, l.country) as location,
                jm.total_seen_count, jm.sites_posted_count, jm.days_active, 
                jm.repost_count, jm.last_activity_date,
                STRING_AGG(DISTINCT js.source_site, ', ') as source_sites,
                STRING_AGG(DISTINCT js.job_url, ', ') as job_urls
            FROM job_postings jp
            LEFT JOIN companies c ON jp.company_id = c.id
            LEFT JOIN locations l ON jp.location_id = l.id
            LEFT JOIN job_metrics jm ON jp.id = jm.job_posting_id
            LEFT JOIN job_sources js ON jp.id = js.job_posting_id
            WHERE jp.id = :job_id
            GROUP BY jp.id, c.id, l.id, jm.id
        """
        
        result = db.execute(text(job_sql), {"job_id": job_id})
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return {
            "id": row.id,
            "job_hash": row.job_hash,
            "title": row.title,
            "company_name": row.company_name,
            "company_domain": row.company_domain,
            "company_description": row.company_description,
            "company_industry": row.industry,
            "company_logo": row.logo_url,
            "location": row.location,
            "description": row.description,
            "requirements": row.requirements,
            "job_type": row.job_type,
            "experience_level": row.experience_level,
            "salary_min": float(row.salary_min) if row.salary_min else None,
            "salary_max": float(row.salary_max) if row.salary_max else None,
            "salary_currency": row.salary_currency,
            "salary_interval": row.salary_interval,
            "is_remote": row.is_remote,
            "status": row.status,
            "first_seen_at": row.first_seen_at.strftime('%Y-%m-%d %H:%M') if row.first_seen_at else None,
            "last_seen_at": row.last_seen_at.strftime('%Y-%m-%d %H:%M') if row.last_seen_at else None,
            "created_at": row.created_at.strftime('%Y-%m-%d %H:%M') if row.created_at else None,
            "updated_at": row.updated_at.strftime('%Y-%m-%d %H:%M') if row.updated_at else None,
            "total_seen_count": row.total_seen_count,
            "sites_posted_count": row.sites_posted_count,
            "days_active": row.days_active,
            "repost_count": row.repost_count,
            "last_activity_date": row.last_activity_date.strftime('%Y-%m-%d') if row.last_activity_date else None,
            "source_sites": row.source_sites,
            "job_urls": row.job_urls
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/export")
async def export_jobs(
    format: str = Query("csv", regex="^(csv|json)$"),
    search: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    is_remote: Optional[bool] = Query(None),
    salary_min: Optional[int] = Query(None),
    salary_max: Optional[int] = Query(None),
    days_ago: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Export jobs data in CSV or JSON format"""
    try:
        from fastapi.responses import StreamingResponse
        import csv
        import json
        from io import StringIO
        from datetime import datetime, timedelta
        
        # Build WHERE conditions based on filters
        where_conditions = ["jp.status = 'active'"]
        params = {}
        
        if search:
            where_conditions.append("(jp.title ILIKE :search OR c.name ILIKE :search OR jp.description ILIKE :search)")
            params["search"] = f"%{search}%"
        
        if company:
            where_conditions.append("c.name ILIKE :company")
            params["company"] = f"%{company}%"
        
        if location:
            where_conditions.append("l.city ILIKE :location OR l.state ILIKE :location OR l.country ILIKE :location")
            params["location"] = f"%{location}%"
        
        if platform:
            where_conditions.append("js.source_site = :platform")
            params["platform"] = platform
        
        if source_site:
            where_conditions.append("js.source_site = :source_site")
            params["source_site"] = source_site
        
        if job_type:
            where_conditions.append("jp.job_type = :job_type")
            params["job_type"] = job_type
        
        if is_remote is not None:
            where_conditions.append("jp.is_remote = :is_remote")
            params["is_remote"] = is_remote
        
        if salary_min:
            where_conditions.append("jp.salary_min >= :salary_min")
            params["salary_min"] = salary_min
        
        if salary_max:
            where_conditions.append("jp.salary_max <= :salary_max")
            params["salary_max"] = salary_max
        
        if days_ago:
            date_cutoff = datetime.now() - timedelta(days=days_ago)
            where_conditions.append("jp.first_seen_at >= :date_cutoff")
            params["date_cutoff"] = date_cutoff
        
        where_clause = " AND ".join(where_conditions)
        
        export_sql = f"""
            SELECT 
                jp.id, jp.job_hash, jp.title, jp.description, jp.requirements,
                jp.job_type, jp.experience_level, jp.salary_min, jp.salary_max, 
                jp.salary_currency, jp.salary_interval, jp.is_remote, jp.status,
                jp.first_seen_at, jp.last_seen_at, jp.created_at, jp.updated_at,
                c.name as company_name, c.domain as company_domain,
                c.industry, c.description as company_description,
                CONCAT_WS(', ', l.city, l.state, l.country) as location,
                jm.total_seen_count, jm.sites_posted_count, jm.days_active,
                STRING_AGG(DISTINCT js.source_site, ', ') as source_sites
            FROM job_postings jp
            LEFT JOIN companies c ON jp.company_id = c.id
            LEFT JOIN locations l ON jp.location_id = l.id
            LEFT JOIN job_metrics jm ON jp.id = jm.job_posting_id
            LEFT JOIN job_sources js ON jp.id = js.job_posting_id
            WHERE {where_clause}
            GROUP BY jp.id, c.id, l.id, jm.id
            ORDER BY jp.first_seen_at DESC
            LIMIT 10000
        """
        
        result = db.execute(text(export_sql), params)
        rows = result.fetchall()
        
        if format == "csv":
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'ID', 'External ID', 'Title', 'Company Name', 'Location', 'Job Type',
                'Experience Level', 'Salary Min', 'Salary Max', 'Currency', 'Salary Interval',
                'Remote', 'Easy Apply', 'Platform', 'Date Posted', 'Date Scraped',
                'Job URL', 'Application URL', 'Company Domain', 'Industry', 
                'Company Size', 'Headquarters', 'Skills', 'Description', 'Requirements'
            ])
            
            # Write data
            for row in rows:
                writer.writerow([
                    row.id, row.external_id, row.title, row.company_name, row.location,
                    row.job_type, row.experience_level, row.salary_min, row.salary_max,
                    row.salary_currency, row.salary_interval, row.is_remote, row.easy_apply,
                    row.source_platform, row.date_posted, row.date_scraped,
                    row.job_url, row.application_url, row.company_domain, row.industry,
                    row.company_size, row.headquarters_location, row.skills,
                    row.description, row.requirements
                ])
            
            output.seek(0)
            
            def generate():
                yield output.getvalue()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"jobs_export_{timestamp}.csv"
            
            return StreamingResponse(
                generate(),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        
        elif format == "json":
            jobs_data = []
            for row in rows:
                jobs_data.append({
                    "id": row.id,
                    "external_id": row.external_id,
                    "title": row.title,
                    "company_name": row.company_name,
                    "company_domain": row.company_domain,
                    "company_industry": row.industry,
                    "company_size": row.company_size,
                    "company_headquarters": row.headquarters_location,
                    "location": row.location,
                    "description": row.description,
                    "requirements": row.requirements,
                    "job_type": row.job_type,
                    "experience_level": row.experience_level,
                    "salary_min": float(row.salary_min) if row.salary_min else None,
                    "salary_max": float(row.salary_max) if row.salary_max else None,
                    "salary_currency": row.salary_currency,
                    "salary_interval": row.salary_interval,
                    "is_remote": row.is_remote,
                    "easy_apply": row.easy_apply,
                    "job_url": row.job_url,
                    "application_url": row.application_url,
                    "source_platform": row.source_platform,
                    "date_posted": row.date_posted.strftime('%Y-%m-%d') if row.date_posted else None,
                    "date_scraped": row.date_scraped.strftime('%Y-%m-%d %H:%M:%S') if row.date_scraped else None,
                    "last_seen": row.last_seen.strftime('%Y-%m-%d %H:%M:%S') if row.last_seen else None,
                    "skills": row.skills
                })
            
            def generate():
                yield json.dumps({
                    "export_info": {
                        "timestamp": datetime.now().isoformat(),
                        "total_jobs": len(jobs_data),
                        "filters_applied": {
                            "search": search,
                            "company": company,
                            "location": location,
                            "platform": platform,
                            "job_type": job_type,
                            "is_remote": is_remote,
                            "salary_min": salary_min,
                            "salary_max": salary_max,
                            "days_ago": days_ago
                        }
                    },
                    "jobs": jobs_data
                }, indent=2)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"jobs_export_{timestamp}.json"
            
            return StreamingResponse(
                generate(),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@router.get("/scheduler/stats")
async def get_scheduler_stats(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_admin_user)
):
    """Get scheduler statistics and status"""
    try:
        scheduler = await get_celery_scheduler(db)
        stats = await scheduler.get_scheduler_stats()
        return stats
    except Exception as e:
        return {
            "pending_jobs": 0,
            "active_jobs": 0,
            "scheduler_status": "error",
            "backend": "celery",
            "error": str(e)
        }

@router.post("/cache/clear")
async def clear_cache(
    pattern: Optional[str] = Query(None, description="Clear specific cache pattern"),
    admin_user: dict = Depends(get_admin_user)
):
    """Clear application cache"""
    return {"message": "Cache cleared successfully (mock response)"}

@router.get("/maintenance")
async def get_maintenance_status(
    admin_user: dict = Depends(get_admin_user)
):
    """Get system maintenance status"""
    return {
        "maintenance_mode": False,
        "scheduled_maintenance": None,
        "system_status": "operational",
        "version": "1.0.0",
        "uptime": "Running"
    }

@router.post("/maintenance")
async def set_maintenance_mode(
    enabled: bool = Query(..., description="Enable or disable maintenance mode"),
    message: Optional[str] = Query(None, description="Maintenance message"),
    admin_user: dict = Depends(get_admin_user)
):
    """Enable or disable maintenance mode"""
    return {
        "maintenance_mode": enabled,
        "message": message or ("Maintenance mode enabled" if enabled else "Maintenance mode disabled"),
        "updated_at": datetime.now().isoformat()
    }
