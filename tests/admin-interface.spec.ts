import { test, expect } from '@playwright/test';

test.describe('JobSpy Admin Interface', () => {
  test('should display admin dashboard with all navigation elements', async ({ page }) => {
    // Navigate to admin dashboard
    await page.goto('/admin/');

    // Verify page title and main heading
    await expect(page.locator('#page-title')).toContainText('JobSpy Admin Panel');
    await expect(page.locator('h1')).toContainText('JobSpy Admin Panel');

    // Verify navigation links are present
    await expect(page.locator('#main-nav')).toBeVisible();

    // Verify quick stats section
    await expect(page.locator('h2:has-text("Quick Stats")')).toBeVisible();
    await expect(page.locator('.stat-card:has-text("Total Searches")')).toBeVisible();
    await expect(page.locator('.stat-card:has-text("Jobs Found Today")')).toBeVisible();
    await expect(page.locator('.stat-card:has-text("Active Searches")')).toBeVisible();
    await expect(page.locator('.stat-card:has-text("System Health")')).toBeVisible();

    // Verify quick actions section
    await expect(page.locator('h2:has-text("Quick Actions")')).toBeVisible();
    await expect(page.locator('a.quick-action:has-text("Manage Searches")')).toBeVisible();
    await expect(page.locator('a.quick-action:has-text("Scheduler")')).toBeVisible();
    await expect(page.locator('a.quick-action:has-text("Jobs Database")')).toBeVisible();
    await expect(page.locator('a.quick-action:has-text("Search Templates")')).toBeVisible();
    await expect(page.locator('a.quick-action:has-text("Analytics")')).toBeVisible();
    await expect(page.locator('a.quick-action:has-text("System Settings")')).toBeVisible();
  });

  test('should allow filling out job search form', async ({ page }) => {
    // Navigate to admin dashboard
    await page.goto('/admin/');

    // Verify quick search form is visible
    await expect(page.locator('h2:has-text("Quick Search")')).toBeVisible();
    await expect(page.locator('h3:has-text("Schedule New Job Search")')).toBeVisible();

    // Fill out the search form
    await page.locator('#quick-search-name-input').fill('Test Search Senior Developer');
    await page.locator('#quick-search-term-input').fill('senior developer');
    await page.locator('#quick-search-location-input').fill('New York, NY');

    // Verify form fields are filled correctly
    await expect(page.locator('#quick-search-name-input')).toHaveValue('Test Search Senior Developer');
    await expect(page.locator('#quick-search-term-input')).toHaveValue('senior developer');
    await expect(page.locator('#quick-search-location-input')).toHaveValue('New York, NY');

    // Verify job sites selection
    const jobSitesListbox = page.locator('#quick-search-job-sites-select');
    await expect(jobSitesListbox).toHaveValues(['indeed', 'linkedin']);

    // Verify results per site spinner has default value
    await expect(page.locator('#quick-search-results-per-site-input')).toHaveValue('50');

    // Verify recurring search checkbox is available
    await expect(page.locator('#quick-search-recurring-checkbox')).toBeVisible();

    // Verify schedule search button is present
    await expect(page.locator('button:has-text("Schedule Search")')).toBeVisible();
  });

  test('should navigate to searches management page', async ({ page }) => {
    // Navigate to searches page
    await page.goto('/admin/searches');

    // Verify page title and heading
    await expect(page.locator('#page-title')).toContainText('JobSpy Admin - Searches');
    await expect(page.locator('h1')).toContainText('Search Management');

    // Verify search statistics section
    await expect(page.locator('h2:has-text("Search Statistics")')).toBeVisible();
    await expect(page.locator('.stat-card:has-text("Total Searches")')).toBeVisible();
    await expect(page.locator('.stat-card:has-text("Active Searches")')).toBeVisible();
    await expect(page.locator('.stat-card:has-text("Completed Today")')).toBeVisible();
    await expect(page.locator('.stat-card:has-text("Success Rate")')).toBeVisible();

    // Verify quick actions section
    await expect(page.locator('h2:has-text("Quick Actions")')).toBeVisible();
    await expect(page.locator('button:has-text("Quick Search (Immediate)")')).toBeVisible();
    await expect(page.locator('button:has-text("API Documentation")')).toBeVisible();

    // Verify schedule future search form
    await expect(page.locator('h2:has-text("Schedule Future Search")')).toBeVisible();
    await expect(page.locator('#search-name-input')).toBeVisible();
    await expect(page.locator('#search-term-input')).toBeVisible();
    await expect(page.locator('#location-input')).toBeVisible();
    await expect(page.locator('#job-sites-select')).toBeVisible();
    await expect(page.locator('#results-per-site-input')).toBeVisible();
    await expect(page.locator('#job-type-select')).toBeVisible();
    await expect(page.locator('#schedule-type-select')).toBeVisible();
    await expect(page.locator('button:has-text("Schedule Search")')).toBeVisible();

    // Verify bulk search operations section
    await expect(page.locator('h2:has-text("Bulk Search Operations")')).toBeVisible();
    await expect(page.locator('button:has-text("Add Search")')).toBeVisible();
    await expect(page.locator('button:has-text("Clear All")')).toBeVisible();
    await expect(page.locator('button:has-text("Load Template")').first()).toBeVisible();

    // Verify scheduled searches section
    await expect(page.locator('h2:has-text("Scheduled Searches")')).toBeVisible();
    await expect(page.locator('button:has-text("Refresh")')).toBeVisible();
    await expect(page.locator('button:has-text("Cancel All Pending")')).toBeVisible();
    await expect(page.locator('button:has-text("Clean Up Old Jobs")')).toBeVisible();
    await expect(page.locator('button:has-text("Export")')).toBeVisible();

    // Verify the searches table with proper headers
    await expect(page.locator('table.scheduled-searches-table')).toBeVisible();
    const headers = ['ID', 'Name', 'Search Term', 'Location', 'Sites', 'Status', 'Scheduled', 'Jobs Found', 'Run Count', 'Actions'];
    for (const header of headers) {
        await expect(page.locator(`table.scheduled-searches-table th:has-text("${header}")`)).toBeVisible();
    }

    // Verify empty state message
    await expect(page.locator('.empty-state h3')).toContainText('No searches found');
    await expect(page.locator('.empty-state p')).toContainText('Create your first search using the form above.');
  });

  test('should fill out future search form with all fields', async ({ page }) => {
    // Navigate to searches page
    await page.goto('/admin/searches');

    // Fill out the future search form
    await page.locator('#search-name-input').fill('Future Test Search');
    await page.locator('#search-term-input').fill('javascript developer');
    await page.locator('#location-input').fill('Remote');

    // Select job type from dropdown
    await page.locator('#job-type-select').selectOption('fulltime');

    // Change results per site
    await page.locator('#results-per-site-input').fill('30');

    // Verify form fields are filled correctly
    await expect(page.locator('#search-name-input')).toHaveValue('Future Test Search');
    await expect(page.locator('#search-term-input')).toHaveValue('javascript developer');
    await expect(page.locator('#location-input')).toHaveValue('Remote');
    await expect(page.locator('#job-type-select')).toHaveValue('fulltime');
    await expect(page.locator('#results-per-site-input')).toHaveValue('30');

    // Verify schedule type options
    const scheduleTypeCombobox = page.locator('#schedule-type-select');
    await expect(scheduleTypeCombobox).toHaveValue('scheduled');
    
    // Test changing to recurring
    await scheduleTypeCombobox.selectOption('recurring');
    await expect(scheduleTypeCombobox).toHaveValue('recurring');

    // Verify job sites are pre-selected
    const jobSitesListbox = page.locator('#job-sites-select');
    await expect(jobSitesListbox).toHaveValues(['indeed', 'linkedin']);
  });
});