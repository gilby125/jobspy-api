import { test, expect } from '@playwright/test';

test.describe('JobSpy Admin - Complete Route Coverage', () => {
  
  test.describe('Dashboard Routes', () => {
    test('should navigate to main dashboard', async ({ page }) => {
      await page.goto('/admin/');
      await expect(page.locator('#page-title')).toContainText('JobSpy Admin Panel');
      await expect(page.locator('h1')).toContainText('JobSpy Admin Panel');
      await expect(page.locator('.subtitle')).toContainText('Manage job searches, monitor system health, and configure settings');
    });

    test('should display all navigation links', async ({ page }) => {
      await page.goto('/admin/');
      
      const expectedLinks = [
        { name: 'Dashboard', url: '/admin/' },
        { name: 'Searches', url: '/admin/searches' },
        { name: 'Scheduler', url: '/admin/scheduler' },
        { name: 'Jobs', url: '/admin/jobs/page' },
        { name: 'Templates', url: '/admin/templates' },
        { name: 'Analytics', url: '/admin/analytics' },
        { name: 'Settings', url: '/admin/settings' }
      ];

      for (const link of expectedLinks) {
        const navLink = page.getByRole('link', { name: link.name, exact: true });
        await expect(navLink).toBeVisible();
        await expect(navLink).toHaveAttribute('href', link.url);
      }
    });
  });

  test.describe('Scheduler Route (/admin/scheduler)', () => {
    test('should display scheduler interface with controls', async ({ page }) => {
      await page.goto('/admin/scheduler');
      await expect(page.locator('#page-title')).toContainText('Scheduler - JobSpy Admin');
      await expect(page.locator('h1')).toContainText('JobSpy Scheduler');

      // Verify scheduler status section
      await expect(page.locator('h2:has-text("Scheduler Status")')).toBeVisible();
      await expect(page.locator('.stat-card:has-text("Pending Jobs")')).toBeVisible();
      await expect(page.locator('.stat-card:has-text("Active Jobs")')).toBeVisible();
      await expect(page.locator('.stat-card:has-text("Scheduler Status")')).toBeVisible();
      await expect(page.locator('.stat-card:has-text("Backend Type")')).toBeVisible();

      // Verify scheduler controls
      await expect(page.locator('h2:has-text("Scheduler Controls")')).toBeVisible();
      await expect(page.locator('button:has-text("Start Scheduler")')).toBeVisible();
      await expect(page.locator('button:has-text("Stop Scheduler")')).toBeVisible();
      await expect(page.locator('button:has-text("Restart Scheduler")')).toBeVisible();
      await expect(page.locator('button:has-text("Refresh Stats")')).toBeVisible();
    });

    test('should have schedule management features', async ({ page }) => {
      await page.goto('/admin/scheduler');
      
      // Verify schedule management section
      await expect(page.locator('h3:has-text("Schedule Management")')).toBeVisible();
      
      // Test status filter
      const statusFilter = page.locator('#status-filter');
      await expect(statusFilter).toBeVisible();
      
      // Test limit input
      const limitInput = page.locator('#limit-input');
      await expect(limitInput).toHaveValue('50');
      
      // Test action buttons
      await expect(page.locator('button:has-text("Filter")')).toBeVisible();
      await expect(page.locator('button:has-text("Cancel All Pending")')).toBeVisible();
      await expect(page.locator('button:has-text("Retry Failed Jobs")')).toBeVisible();
      await expect(page.locator('button:has-text("Export Schedule")')).toBeVisible();
    });

    test('should display scheduled jobs table and logs', async ({ page }) => {
      await page.goto('/admin/scheduler');
      
      // Verify scheduled jobs section
      await expect(page.locator('h2:has-text("Scheduled Jobs")')).toBeVisible();
      await expect(page.locator('table.scheduled-jobs-table')).toBeVisible();
      
      // Verify table headers
      const headers = ['ID', 'Name', 'Search Term', 'Location', 'Sites', 'Status', 'Scheduled', 'Jobs Found', 'Recurring', 'Actions'];
      for (const header of headers) {
        await expect(page.locator(`th:has-text("${header}")`)).toBeVisible();
      }
      
      // Verify scheduler logs section
      await expect(page.locator('h2:has-text("Scheduler Logs")')).toBeVisible();
      await expect(page.locator('button:has-text("Refresh Logs")')).toBeVisible();
      await expect(page.locator('button:has-text("Clear Logs")')).toBeVisible();
    });
  });

  test.describe('Jobs Database Route (/admin/jobs/page)', () => {
    test('should display jobs database with statistics', async ({ page }) => {
      await page.goto('/admin/jobs/page');
      await expect(page.locator('#page-title')).toContainText('Jobs Database - JobSpy Admin');
      await expect(page.locator('h1')).toContainText('Jobs Database');

      // Verify database statistics
      await expect(page.locator('h2:has-text("Database Statistics")')).toBeVisible();
      await expect(page.locator('.stat-card:has-text("Total Jobs")')).toBeVisible();
      await expect(page.locator('.stat-card:has-text("Active Jobs")')).toBeVisible();
      await expect(page.locator('.stat-card:has-text("Companies")')).toBeVisible();
      await expect(page.locator('.stat-card:has-text("Latest Scrape")')).toBeVisible();
    });

    test('should have comprehensive filtering capabilities', async ({ page }) => {
      await page.goto('/admin/jobs/page');
      
      // Verify filters section
      await expect(page.locator('h2:has-text("Filters & Search")')).toBeVisible();
      
      // Test search inputs
      await expect(page.locator('#search-input')).toBeVisible();
      await expect(page.locator('#location-input')).toBeVisible();
      
      // Test dropdown filters
      await expect(page.locator('#company-filter')).toBeVisible();
      await expect(page.locator('#platform-filter')).toBeVisible();
      await expect(page.locator('#job-type-filter')).toBeVisible();
      await expect(page.locator('#remote-filter')).toBeVisible();
      await expect(page.locator('#date-posted-filter')).toBeVisible();
      await expect(page.locator('#results-per-page-filter')).toBeVisible();
      
      // Test salary inputs
      await expect(page.locator('#salary-min-input')).toBeVisible();
      await expect(page.locator('#salary-max-input')).toBeVisible();
      
      // Test action buttons
      await expect(page.locator('button:has-text("Apply Filters")')).toBeVisible();
      await expect(page.locator('button:has-text("Clear")')).toBeVisible();
      await expect(page.locator('button:has-text("Export CSV")')).toBeVisible();
      await expect(page.locator('button:has-text("Export JSON")')).toBeVisible();
      await expect(page.locator('button:has-text("Refresh")')).toBeVisible();
    });

    test('should display job listings table', async ({ page }) => {
      await page.goto('/admin/jobs/page');
      
      // Verify job listings section
      await expect(page.locator('h2:has-text("Job Listings")')).toBeVisible();
      await expect(page.locator('table.job-listings-table')).toBeVisible();
      
      // Verify table headers
      const headers = ['Title', 'Company', 'Location', 'Salary', 'Type', 'Remote', 'Platform', 'Posted', 'Actions'];
      for (const header of headers) {
        await expect(page.locator(`th:has-text("${header}")`)).toBeVisible();
      }
      
      // Verify empty state
      await expect(page.locator('.empty-state h3')).toContainText('No jobs found');
    });
  });

  test.describe('Job Browser Route (/admin/jobs/browse)', () => {
    test('should display job browser interface', async ({ page }) => {
      await page.goto('/admin/jobs/browse');
      await expect(page.locator('#page-title')).toContainText('Job Browser - JobSpy Admin');
      await expect(page.locator('h1')).toContainText('Job Browser');
      await expect(page.locator('.subtitle')).toContainText('Browse and search through available job listings');
    });

    test('should have search functionality', async ({ page }) => {
      await page.goto('/admin/jobs/browse');
      
      // Verify search section
      await expect(page.locator('h2:has-text("Search Jobs")')).toBeVisible();
      
      // Test search inputs
      await expect(page.locator('#search-term-input')).toBeVisible();
      await expect(page.locator('#location-input')).toBeVisible();
      
      // Test job sites selection
      await expect(page.locator('#job-sites-select')).toBeVisible();
      
      // Test dropdown filters
      await expect(page.locator('#job-type-select')).toBeVisible();
      await expect(page.locator('#results-select')).toBeVisible();
      await expect(page.locator('#country-select')).toBeVisible();
      
      // Test action buttons
      await expect(page.locator('button:has-text("Search Jobs")')).toBeVisible();
      await expect(page.locator('button:has-text("Clear")')).toBeVisible();
      await expect(page.locator('button:has-text("Load Sample")')).toBeVisible();
      
      // Verify job listings section
      await expect(page.locator('h2:has-text("Job Listings")')).toBeVisible();
    });
  });

  test.describe('Templates Route (/admin/templates)', () => {
    test('should display templates management interface', async ({ page }) => {
      await page.goto('/admin/templates');
      await expect(page.locator('#page-title')).toContainText('Search Templates - JobSpy Admin');
      await expect(page.locator('h1')).toContainText('Search Templates');
      await expect(page.locator('.subtitle')).toContainText('Create and manage reusable job search templates');

      // Verify template statistics
      await expect(page.locator('h2:has-text("Template Statistics")')).toBeVisible();
      await expect(page.locator('.stat-card:has-text("Total Templates")')).toBeVisible();
      await expect(page.locator('.stat-card:has-text("Recently Used")')).toBeVisible();
      await expect(page.locator('.stat-card:has-text("Most Popular")')).toBeVisible();
    });

    test('should have template creation form', async ({ page }) => {
      await page.goto('/admin/templates');
      
      // Verify template creation section
      await expect(page.locator('h2:has-text("Create New Template")')).toBeVisible();
      
      // Test form inputs
      await expect(page.locator('#template-name-input')).toBeVisible();
      await expect(page.locator('#description-input')).toBeVisible();
      await expect(page.locator('#search-term-input')).toBeVisible();
      await expect(page.locator('#location-input')).toBeVisible();
      await expect(page.locator('#tags-input')).toBeVisible();
      
      // Test dropdown filters
      await expect(page.locator('#job-sites-select')).toBeVisible();
      await expect(page.locator('#job-type-select')).toBeVisible();
      await expect(page.locator('#remote-select')).toBeVisible();
      await expect(page.locator('#default-results-select')).toBeVisible();
      await expect(page.locator('#country-select')).toBeVisible();
      
      // Test action buttons
      await expect(page.locator('button:has-text("Save Template")')).toBeVisible();
      await expect(page.locator('button:has-text("Clear Form")')).toBeVisible();
      await expect(page.locator('button:has-text("Test Template")')).toBeVisible();
    });

    test('should display saved templates section', async ({ page }) => {
      await page.goto('/admin/templates');
      
      // Verify saved templates section
      await expect(page.locator('h2:has-text("Saved Templates")')).toBeVisible();
      
      // Verify empty state
      await expect(page.locator('.empty-state h3')).toContainText('No templates found');
      await expect(page.locator('.empty-state p')).toContainText('Create your first search template using the form above.');
    });
  });

  test.describe('Analytics Route (/admin/analytics)', () => {
    test('should display analytics dashboard with metrics', async ({ page }) => {
      await page.goto('/admin/analytics');
      await expect(page.locator('#page-title')).toContainText('Analytics - JobSpy Admin');
      await expect(page.locator('h1')).toContainText('JobSpy Analytics');
      await expect(page.locator('.subtitle')).toContainText('Detailed insights into job search performance and trends');

      // Verify key metrics
      await expect(page.locator('h2:has-text("Key Metrics")')).toBeVisible();
      await expect(page.locator('.stat-card:has-text("Total Searches")')).toBeVisible();
      await expect(page.locator('.stat-card:has-text("Success Rate")')).toBeVisible();
      await expect(page.locator('.stat-card:has-text("Avg Results per Search")')).toBeVisible();
      await expect(page.locator('.stat-card:has-text("Active Searches")')).toBeVisible();
    });

    test('should display search trends and data tables', async ({ page }) => {
      await page.goto('/admin/analytics');
      
      // Verify search trends section
      await expect(page.locator('h2:has-text("Search Trends")')).toBeVisible();
      await expect(page.locator('#search-trends-chart')).toBeVisible();
      
      // Verify recent searches table
      await expect(page.locator('h2:has-text("Recent Searches")')).toBeVisible();
      const recentSearchesTable = page.locator('table.recent-searches-table');
      await expect(recentSearchesTable).toBeVisible();
      
      // Verify recent searches headers
      const recentHeaders = ['Search Term', 'Location', 'Site', 'Results', 'Status', 'Time'];
      for (const header of recentHeaders) {
        await expect(recentSearchesTable.locator(`th:has-text("${header}")`)).toBeVisible();
      }
      
      // Verify popular search terms table
      await expect(page.locator('h2:has-text("Popular Search Terms")')).toBeVisible();
      const popularTermsTable = page.locator('table.popular-terms-table');
      await expect(popularTermsTable).toBeVisible();
      
      // Verify popular terms headers
      const popularHeaders = ['Search Term', 'Frequency', 'Avg Results', 'Success Rate'];
      for (const header of popularHeaders) {
        await expect(popularTermsTable.locator(`th:has-text("${header}")`)).toBeVisible();
      }
    });

    test('should display actual analytics data', async ({ page }) => {
      await page.goto('/admin/analytics');
      
      // Verify some sample data is shown (from the snapshot)
      await expect(page.locator('td:has-text("product manager")')).toBeVisible();
      await expect(page.locator('td:has-text("software engineer")')).toBeVisible();
      await expect(page.locator('td:has-text("data scientist")')).toBeVisible();
      await expect(page.locator('td:has-text("marketing manager")')).toBeVisible();
      await expect(page.locator('td:has-text("python developer")')).toBeVisible();
    });
  });

  test.describe('Settings Route (/admin/settings)', () => {
    test('should display settings interface', async ({ page }) => {
      await page.goto('/admin/settings');
      await expect(page.locator('#page-title')).toContainText('Admin Settings - JobSpy');
      await expect(page.locator('h1')).toContainText('JobSpy Admin Settings');
      await expect(page.locator('.subtitle')).toContainText('Configure system parameters and preferences');
    });

    test('should have system configuration sections', async ({ page }) => {
      await page.goto('/admin/settings');
      
      // Verify main configuration section
      await expect(page.locator('h2:has-text("System Configuration")')).toBeVisible();
      
      // Verify search settings
      await expect(page.locator('h3:has-text("Search Settings")')).toBeVisible();
      await expect(page.locator('label:has-text("Max Concurrent Searches:")')).toBeVisible();
      await expect(page.locator('label:has-text("Default Results per Search:")')).toBeVisible();
      await expect(page.locator('label:has-text("Default Job Sites:")')).toBeVisible();
      
      // Verify performance settings
      await expect(page.locator('h3:has-text("Performance Settings")')).toBeVisible();
      await expect(page.locator('label:has-text("Rate Limit (requests per hour):")')).toBeVisible();
      await expect(page.locator('label:has-text("Cache Enabled:")')).toBeVisible();
      await expect(page.locator('label:has-text("Cache Expiry (seconds):")')).toBeVisible();
      
      // Verify security settings
      await expect(page.locator('h3:has-text("Security Settings")')).toBeVisible();
      await expect(page.locator('label:has-text("API Key Authentication:")')).toBeVisible();
      await expect(page.locator('label:has-text("Maintenance Mode:")')).toBeVisible();
    });

    test('should have functional form controls', async ({ page }) => {
      await page.goto('/admin/settings');
      
      // Test numeric inputs have default values
      const maxConcurrentInput = page.locator('#max-concurrent-searches-input');
      await expect(maxConcurrentInput).toHaveValue('5');
      
      const defaultResultsInput = page.locator('#default-results-input');
      await expect(defaultResultsInput).toHaveValue('20');
      
      const rateLimitInput = page.locator('#rate-limit-input');
      await expect(rateLimitInput).toHaveValue('100');
      
      const cacheExpiryInput = page.locator('#cache-expiry-input');
      await expect(cacheExpiryInput).toHaveValue('3600');
      
      // Test action buttons
      await expect(page.locator('button:has-text("Save Settings")')).toBeVisible();
      await expect(page.locator('button:has-text("Reload")')).toBeVisible();
    });
  });

  test.describe('Cross-Route Navigation', () => {
    test('should navigate between all admin routes correctly', async ({ page }) => {
      const routes = [
        { path: '/admin/', title: 'JobSpy Admin Panel' },
        { path: '/admin/searches', title: 'JobSpy Admin - Searches' },
        { path: '/admin/scheduler', title: 'Scheduler - JobSpy Admin' },
        { path: '/admin/jobs/page', title: 'Jobs Database - JobSpy Admin' },
        { path: '/admin/jobs/browse', title: 'Job Browser - JobSpy Admin' },
        { path: '/admin/templates', title: 'Search Templates - JobSpy Admin' },
        { path: '/admin/analytics', title: 'Analytics - JobSpy Admin' },
        { path: '/admin/settings', title: 'Admin Settings - JobSpy' }
      ];

      for (const route of routes) {
        await page.goto(route.path);
        await expect(page).toHaveTitle(route.title);
        
        // Verify navigation is present on each page
        await expect(page.locator('#main-nav')).toBeVisible();
      }
    });
  });
});