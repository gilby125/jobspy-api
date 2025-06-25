import { test, expect } from '@playwright/test';

test.describe('JobSpy Admin - Complete Route Coverage', () => {
  
  test.describe('Dashboard Routes', () => {
    test('should navigate to main dashboard', async ({ page }) => {
      await page.goto('/admin/');
      await expect(page).toHaveTitle('JobSpy Admin Panel');
      await expect(page.getByRole('heading', { name: '🔧 JobSpy Admin Panel', level: 1 })).toBeVisible();
      await expect(page.getByText('Manage job searches, monitor system health, and configure settings')).toBeVisible();
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
      await expect(page).toHaveTitle('Scheduler - JobSpy Admin');
      await expect(page.getByRole('heading', { name: '⚙️ JobSpy Scheduler', level: 1 })).toBeVisible();

      // Verify scheduler status section
      await expect(page.getByRole('heading', { name: 'Scheduler Status', level: 2 })).toBeVisible();
      await expect(page.getByText('Pending Jobs').first()).toBeVisible();
      await expect(page.getByText('Active Jobs').first()).toBeVisible();
      await expect(page.getByText('Scheduler Status').first()).toBeVisible();
      await expect(page.getByText('Backend Type')).toBeVisible();

      // Verify scheduler controls
      await expect(page.getByRole('heading', { name: 'Scheduler Controls', level: 2 })).toBeVisible();
      await expect(page.getByRole('button', { name: '▶️ Start Scheduler' })).toBeVisible();
      await expect(page.getByRole('button', { name: '⏸️ Stop Scheduler' })).toBeVisible();
      await expect(page.getByRole('button', { name: '🔄 Restart Scheduler' })).toBeVisible();
      await expect(page.getByRole('button', { name: '📊 Refresh Stats' })).toBeVisible();
    });

    test('should have schedule management features', async ({ page }) => {
      await page.goto('/admin/scheduler');
      
      // Verify schedule management section
      await expect(page.getByRole('heading', { name: 'Schedule Management', level: 3 })).toBeVisible();
      
      // Test status filter
      const statusFilter = page.getByText('Filter by Status:').locator('..').locator('select');
      await expect(statusFilter).toBeVisible();
      
      // Test limit input
      const limitInput = page.getByRole('spinbutton').first();
      await expect(limitInput).toHaveValue('50');
      
      // Test action buttons
      await expect(page.getByRole('button', { name: '🔍 Filter' })).toBeVisible();
      await expect(page.getByRole('button', { name: '❌ Cancel All Pending' })).toBeVisible();
      await expect(page.getByRole('button', { name: '🔄 Retry Failed Jobs' })).toBeVisible();
      await expect(page.getByRole('button', { name: '📁 Export Schedule' })).toBeVisible();
    });

    test('should display scheduled jobs table and logs', async ({ page }) => {
      await page.goto('/admin/scheduler');
      
      // Verify scheduled jobs section
      await expect(page.getByRole('heading', { name: 'Scheduled Jobs', level: 2 })).toBeVisible();
      await expect(page.getByRole('table')).toBeVisible();
      
      // Verify table headers
      const headers = ['ID', 'Name', 'Search Term', 'Location', 'Sites', 'Status', 'Scheduled', 'Jobs Found', 'Recurring', 'Actions'];
      for (const header of headers) {
        await expect(page.getByRole('cell', { name: header })).toBeVisible();
      }
      
      // Verify scheduler logs section
      await expect(page.getByRole('heading', { name: 'Scheduler Logs', level: 2 })).toBeVisible();
      await expect(page.getByRole('button', { name: '🔄 Refresh Logs' })).toBeVisible();
      await expect(page.getByRole('button', { name: '🗑️ Clear Logs' })).toBeVisible();
    });
  });

  test.describe('Jobs Database Route (/admin/jobs/page)', () => {
    test('should display jobs database with statistics', async ({ page }) => {
      await page.goto('/admin/jobs/page');
      await expect(page).toHaveTitle('Jobs Database - JobSpy Admin');
      await expect(page.getByRole('heading', { name: '💼 Jobs Database', level: 1 })).toBeVisible();

      // Verify database statistics
      await expect(page.getByRole('heading', { name: 'Database Statistics', level: 2 })).toBeVisible();
      await expect(page.getByText('Total Jobs').first()).toBeVisible();
      await expect(page.getByText('Active Jobs').first()).toBeVisible();
      await expect(page.getByText('Companies').first()).toBeVisible();
      await expect(page.getByText('Latest Scrape')).toBeVisible();
    });

    test('should have comprehensive filtering capabilities', async ({ page }) => {
      await page.goto('/admin/jobs/page');
      
      // Verify filters section
      await expect(page.getByRole('heading', { name: 'Filters & Search', level: 2 })).toBeVisible();
      
      // Test search inputs
      await expect(page.getByRole('textbox', { name: 'Search title, company, or description...' })).toBeVisible();
      await expect(page.getByRole('textbox', { name: 'Enter location...' })).toBeVisible();
      
      // Test dropdown filters
      await expect(page.getByText('Company:').locator('..').locator('select')).toBeVisible();
      await expect(page.getByText('Platform:').locator('..').locator('select')).toBeVisible();
      await expect(page.getByText('Job Type:').locator('..').locator('select')).toBeVisible();
      await expect(page.getByText('Remote:').locator('..').locator('select')).toBeVisible();
      await expect(page.getByText('Date Posted:').locator('..').locator('select')).toBeVisible();
      await expect(page.getByText('Results per page:').locator('..').locator('select')).toBeVisible();
      
      // Test salary inputs
      await expect(page.getByText('Salary Min:').locator('..').locator('input')).toBeVisible();
      await expect(page.getByText('Salary Max:').locator('..').locator('input')).toBeVisible();
      
      // Test action buttons
      await expect(page.getByRole('button', { name: '🔍 Apply Filters' })).toBeVisible();
      await expect(page.getByRole('button', { name: '🗑️ Clear' })).toBeVisible();
      await expect(page.getByRole('button', { name: '📊 Export CSV' })).toBeVisible();
      await expect(page.getByRole('button', { name: '📋 Export JSON' })).toBeVisible();
      await expect(page.getByRole('button', { name: '🔄 Refresh' })).toBeVisible();
    });

    test('should display job listings table', async ({ page }) => {
      await page.goto('/admin/jobs/page');
      
      // Verify job listings section
      await expect(page.getByText('Job Listings')).toBeVisible();
      await expect(page.getByRole('table')).toBeVisible();
      
      // Verify table headers
      const headers = ['Title', 'Company', 'Location', 'Salary', 'Type', 'Remote', 'Platform', 'Posted', 'Actions'];
      for (const header of headers) {
        await expect(page.getByRole('cell', { name: header })).toBeVisible();
      }
      
      // Verify empty state
      await expect(page.getByRole('heading', { name: 'No jobs found', level: 3 })).toBeVisible();
    });
  });

  test.describe('Job Browser Route (/admin/jobs/browse)', () => {
    test('should display job browser interface', async ({ page }) => {
      await page.goto('/admin/jobs/browse');
      await expect(page).toHaveTitle('Job Browser - JobSpy Admin');
      await expect(page.getByRole('heading', { name: '🔍 Job Browser', level: 1 })).toBeVisible();
      await expect(page.getByText('Browse and search through available job listings')).toBeVisible();
    });

    test('should have search functionality', async ({ page }) => {
      await page.goto('/admin/jobs/browse');
      
      // Verify search section
      await expect(page.getByRole('heading', { name: '🔍 Search Jobs', level: 2 })).toBeVisible();
      
      // Test search inputs
      await expect(page.getByRole('textbox', { name: 'Search Term:' })).toBeVisible();
      await expect(page.getByRole('textbox', { name: 'Location:' })).toBeVisible();
      
      // Test job sites selection
      await expect(page.getByRole('listbox', { name: 'Job Sites:' })).toBeVisible();
      
      // Test dropdown filters
      await expect(page.getByRole('combobox', { name: 'Job Type:' })).toBeVisible();
      await expect(page.getByRole('combobox', { name: 'Results:' })).toBeVisible();
      await expect(page.getByRole('combobox', { name: 'Country:' })).toBeVisible();
      
      // Test action buttons
      await expect(page.getByRole('button', { name: '🔍 Search Jobs' })).toBeVisible();
      await expect(page.getByRole('button', { name: '🗑️ Clear' })).toBeVisible();
      await expect(page.getByRole('button', { name: '📋 Load Sample' })).toBeVisible();
      
      // Verify job listings section
      await expect(page.getByRole('heading', { name: '📋 Job Listings', level: 2 })).toBeVisible();
    });
  });

  test.describe('Templates Route (/admin/templates)', () => {
    test('should display templates management interface', async ({ page }) => {
      await page.goto('/admin/templates');
      await expect(page).toHaveTitle('Search Templates - JobSpy Admin');
      await expect(page.getByRole('heading', { name: '📄 Search Templates', level: 1 })).toBeVisible();
      await expect(page.getByText('Create and manage reusable job search templates')).toBeVisible();

      // Verify template statistics
      await expect(page.getByRole('heading', { name: '📊 Template Statistics', level: 2 })).toBeVisible();
      await expect(page.getByText('Total Templates')).toBeVisible();
      await expect(page.getByText('Recently Used')).toBeVisible();
      await expect(page.getByText('Most Popular')).toBeVisible();
    });

    test('should have template creation form', async ({ page }) => {
      await page.goto('/admin/templates');
      
      // Verify template creation section
      await expect(page.getByRole('heading', { name: '➕ Create New Template', level: 2 })).toBeVisible();
      
      // Test form inputs
      await expect(page.getByRole('textbox', { name: 'Template Name:' })).toBeVisible();
      await expect(page.getByRole('textbox', { name: 'Description:' })).toBeVisible();
      await expect(page.getByRole('textbox', { name: 'Search Term:' })).toBeVisible();
      await expect(page.getByRole('textbox', { name: 'Location:' })).toBeVisible();
      await expect(page.getByRole('textbox', { name: 'Tags (optional):' })).toBeVisible();
      
      // Test dropdown filters
      await expect(page.getByRole('listbox', { name: 'Job Sites:' })).toBeVisible();
      await expect(page.getByRole('combobox', { name: 'Job Type:' })).toBeVisible();
      await expect(page.getByRole('combobox', { name: 'Remote:' })).toBeVisible();
      await expect(page.getByRole('combobox', { name: 'Default Results:' })).toBeVisible();
      await expect(page.getByRole('combobox', { name: 'Country:' })).toBeVisible();
      
      // Test action buttons
      await expect(page.getByRole('button', { name: '💾 Save Template' })).toBeVisible();
      await expect(page.getByRole('button', { name: '🗑️ Clear Form' })).toBeVisible();
      await expect(page.getByRole('button', { name: '🧪 Test Template' })).toBeVisible();
    });

    test('should display saved templates section', async ({ page }) => {
      await page.goto('/admin/templates');
      
      // Verify saved templates section
      await expect(page.getByRole('heading', { name: '📋 Saved Templates', level: 2 })).toBeVisible();
      
      // Verify empty state
      await expect(page.getByRole('heading', { name: 'No templates found', level: 3 })).toBeVisible();
      await expect(page.getByText('Create your first search template using the form above.')).toBeVisible();
    });
  });

  test.describe('Analytics Route (/admin/analytics)', () => {
    test('should display analytics dashboard with metrics', async ({ page }) => {
      await page.goto('/admin/analytics');
      await expect(page).toHaveTitle('Analytics - JobSpy Admin');
      await expect(page.getByRole('heading', { name: '📈 JobSpy Analytics', level: 1 })).toBeVisible();
      await expect(page.getByText('Detailed insights into job search performance and trends')).toBeVisible();

      // Verify key metrics
      await expect(page.getByRole('heading', { name: 'Key Metrics', level: 2 })).toBeVisible();
      await expect(page.getByText('Total Searches').first()).toBeVisible();
      await expect(page.getByText('Success Rate').first()).toBeVisible();
      await expect(page.getByText('Avg Results per Search')).toBeVisible();
      await expect(page.getByText('Active Searches').first()).toBeVisible();
    });

    test('should display search trends and data tables', async ({ page }) => {
      await page.goto('/admin/analytics');
      
      // Verify search trends section
      await expect(page.getByRole('heading', { name: 'Search Trends', level: 2 })).toBeVisible();
      await expect(page.getByText('📊 Search trends chart would appear here')).toBeVisible();
      
      // Verify recent searches table
      await expect(page.getByRole('heading', { name: 'Recent Searches', level: 2 })).toBeVisible();
      const recentSearchesTable = page.getByRole('table').first();
      await expect(recentSearchesTable).toBeVisible();
      
      // Verify recent searches headers
      const recentHeaders = ['Search Term', 'Location', 'Site', 'Results', 'Status', 'Time'];
      for (const header of recentHeaders) {
        await expect(recentSearchesTable.getByRole('cell', { name: header })).toBeVisible();
      }
      
      // Verify popular search terms table
      await expect(page.getByRole('heading', { name: 'Popular Search Terms', level: 2 })).toBeVisible();
      const popularTermsTable = page.getByRole('table').nth(1);
      await expect(popularTermsTable).toBeVisible();
      
      // Verify popular terms headers
      const popularHeaders = ['Search Term', 'Frequency', 'Avg Results', 'Success Rate'];
      for (const header of popularHeaders) {
        await expect(popularTermsTable.getByRole('cell', { name: header })).toBeVisible();
      }
    });

    test('should display actual analytics data', async ({ page }) => {
      await page.goto('/admin/analytics');
      
      // Verify some sample data is shown (from the snapshot)
      await expect(page.getByText('product manager').first()).toBeVisible();
      await expect(page.getByText('software engineer').first()).toBeVisible();
      await expect(page.getByText('data scientist').first()).toBeVisible();
      await expect(page.getByText('marketing manager').first()).toBeVisible();
      await expect(page.getByText('python developer').first()).toBeVisible();
    });
  });

  test.describe('Settings Route (/admin/settings)', () => {
    test('should display settings interface', async ({ page }) => {
      await page.goto('/admin/settings');
      await expect(page).toHaveTitle('Admin Settings - JobSpy');
      await expect(page.getByRole('heading', { name: '⚙️ JobSpy Admin Settings', level: 1 })).toBeVisible();
      await expect(page.getByText('Configure system parameters and preferences')).toBeVisible();
    });

    test('should have system configuration sections', async ({ page }) => {
      await page.goto('/admin/settings');
      
      // Verify main configuration section
      await expect(page.getByRole('heading', { name: 'System Configuration', level: 2 })).toBeVisible();
      
      // Verify search settings
      await expect(page.getByRole('heading', { name: 'Search Settings', level: 3 })).toBeVisible();
      await expect(page.getByText('Max Concurrent Searches:')).toBeVisible();
      await expect(page.getByText('Default Results per Search:')).toBeVisible();
      await expect(page.getByText('Default Job Sites:')).toBeVisible();
      
      // Verify performance settings
      await expect(page.getByRole('heading', { name: 'Performance Settings', level: 3 })).toBeVisible();
      await expect(page.getByText('Rate Limit (requests per hour):')).toBeVisible();
      await expect(page.getByText('Cache Enabled:')).toBeVisible();
      await expect(page.getByText('Cache Expiry (seconds):')).toBeVisible();
      
      // Verify security settings
      await expect(page.getByRole('heading', { name: 'Security Settings', level: 3 })).toBeVisible();
      await expect(page.getByText('API Key Authentication:')).toBeVisible();
      await expect(page.getByText('Maintenance Mode:')).toBeVisible();
    });

    test('should have functional form controls', async ({ page }) => {
      await page.goto('/admin/settings');
      
      // Test numeric inputs have default values
      const maxConcurrentInput = page.getByText('Max Concurrent Searches:').locator('..').locator('input');
      await expect(maxConcurrentInput).toHaveValue('5');
      
      const defaultResultsInput = page.getByText('Default Results per Search:').locator('..').locator('input');
      await expect(defaultResultsInput).toHaveValue('20');
      
      const rateLimitInput = page.getByText('Rate Limit (requests per hour):').locator('..').locator('input');
      await expect(rateLimitInput).toHaveValue('100');
      
      const cacheExpiryInput = page.getByText('Cache Expiry (seconds):').locator('..').locator('input');
      await expect(cacheExpiryInput).toHaveValue('3600');
      
      // Test action buttons
      await expect(page.getByRole('button', { name: '💾 Save Settings' })).toBeVisible();
      await expect(page.getByRole('button', { name: '🔄 Reload' })).toBeVisible();
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
        await expect(page.getByRole('link', { name: 'Dashboard', exact: true })).toBeVisible();
      }
    });
  });
});