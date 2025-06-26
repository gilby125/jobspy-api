import { test, expect } from '@playwright/test';

test.describe('JobSpy Admin - Searches Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/admin/searches');
  });

  test('should display search statistics dashboard', async ({ page }) => {
    await expect(page.locator('#page-title')).toContainText('JobSpy Admin - Searches');
    await expect(page.locator('h1')).toContainText('Search Management');
    await expect(page.locator('.subtitle')).toContainText('Schedule, monitor, and manage job searches');

    // Verify search statistics section with all metrics
    await expect(page.locator('h2:has-text("Search Statistics")')).toBeVisible();
    await expect(page.locator('.stat-card:has-text("Total Searches")')).toBeVisible();
    await expect(page.locator('.stat-card:has-text("Active Searches")')).toBeVisible();
    await expect(page.locator('.stat-card:has-text("Completed Today")')).toBeVisible();
    await expect(page.locator('.stat-card:has-text("Success Rate")')).toBeVisible();

    // Verify numeric values are displayed (should be "0" for new system)
    await expect(page.locator('.stat-card .value').first()).toContainText('0');
  });

  test('should display quick actions section with working buttons', async ({ page }) => {
    // Verify Quick Actions section
    await expect(page.locator('h2:has-text("Quick Actions")')).toBeVisible();
    await expect(page.locator('p:has-text("For immediate job searches, use the direct search API:")')).toBeVisible();
    
    // Verify buttons are visible and clickable
    await expect(page.locator('button:has-text("Quick Search (Immediate)")')).toBeVisible();
    await expect(page.locator('button:has-text("API Documentation")')).toBeVisible();
    
    // Verify explanatory text
    await expect(page.locator('p:has-text("Quick Search opens the direct API interface for immediate job searches. Use the scheduler below for future or recurring searches.")')).toBeVisible();

    // Test button interactions
    await page.locator('button:has-text("Quick Search (Immediate)")').click();
    await page.locator('button:has-text("API Documentation")').click();
  });

  test('should handle future search form with all field types', async ({ page }) => {
    // Verify Schedule Future Search form
    await expect(page.locator('h2:has-text("Schedule Future Search")')).toBeVisible();

    // Test all input fields
    await page.locator('#search-name-input').fill('Test Future Search');
    await page.locator('#search-term-input').fill('software engineer');
    await page.locator('#location-input').fill('San Francisco, CA');

    // Test job sites multi-select
    const jobSitesListbox = page.locator('#job-sites-select');
    await expect(jobSitesListbox).toBeVisible();

    // Test numeric input
    await page.locator('#results-per-site-input').fill('50');
    await expect(page.locator('#results-per-site-input')).toHaveValue('50');

    // Test job type dropdown
    const jobTypeCombobox = page.locator('#job-type-select');
    await expect(jobTypeCombobox).toHaveValue('');
    await jobTypeCombobox.selectOption('fulltime');
    await expect(jobTypeCombobox).toHaveValue('fulltime');

    // Test schedule type dropdown
    const scheduleTypeCombobox = page.locator('#schedule-type-select');
    await expect(scheduleTypeCombobox).toHaveValue('scheduled');
    await scheduleTypeCombobox.selectOption('recurring');
    await expect(scheduleTypeCombobox).toHaveValue('recurring');

    // Test datetime input
    const scheduleTimeInput = page.locator('#schedule-time-input');
    await expect(scheduleTimeInput).toBeVisible();

    // Test optional description field
    await page.locator('#description-input').fill('Test search description for automated testing');

    // Verify action buttons
    await expect(page.locator('button:has-text("Schedule Search")')).toBeVisible();
    await expect(page.locator('button:has-text("Clear Form")')).toBeVisible();
    await expect(page.locator('button:has-text("Load Template")')).toBeVisible();
  });

  test('should handle bulk search operations', async ({ page }) => {
    // Verify Bulk Search Operations section
    await expect(page.locator('h2:has-text("Bulk Search Operations")')).toBeVisible();
    await expect(page.locator('p:has-text("Schedule multiple searches at once with different parameters")')).toBeVisible();

    // Test batch naming
    await page.locator('#batch-name-input').fill('Engineering Jobs Batch');
    await expect(page.locator('#batch-name-input')).toHaveValue('Engineering Jobs Batch');

    // Test bulk operation buttons
    await expect(page.locator('button:has-text("Add Search")')).toBeVisible();
    await expect(page.locator('button:has-text("Clear All")')).toBeVisible();
    await expect(page.locator('button:has-text("Load Template")').nth(1)).toBeVisible();

    // Verify first search form is present
    await expect(page.locator('.bulk-search-item').first()).toBeVisible();
    await expect(page.locator('.bulk-search-item').first().locator('button:has-text("Remove")')).toBeVisible();

    // Fill out the first bulk search
    await page.locator('.bulk-search-item').first().locator('input[placeholder="e.g. Python Remote Jobs"]').fill('Senior Python Developer Jobs');
    await page.locator('.bulk-search-item').first().locator('input[placeholder="e.g. Python Developer"]').fill('senior python developer');
    await page.locator('.bulk-search-item').first().locator('input[placeholder="e.g. San Francisco, CA"]').fill('Remote');

    // Verify bulk search form fields are filled
    await expect(page.locator('.bulk-search-item').first().locator('input[placeholder="e.g. Python Remote Jobs"]')).toHaveValue('Senior Python Developer Jobs');
    await expect(page.locator('.bulk-search-item').first().locator('input[placeholder="e.g. Python Developer"]')).toHaveValue('senior python developer');
    await expect(page.locator('.bulk-search-item').first().locator('input[placeholder="e.g. San Francisco, CA"]')).toHaveValue('Remote');

    // Test bulk action buttons
    await expect(page.locator('button:has-text("Schedule All Searches")')).toBeVisible();
    await expect(page.locator('button:has-text("Preview")')).toBeVisible();

    // Test preview functionality
    await page.locator('button:has-text("Preview")').click();
  });

  test('should display scheduled searches table with proper structure', async ({ page }) => {
    // Verify Scheduled Searches section
    await expect(page.locator('h2:has-text("Scheduled Searches")')).toBeVisible();

    // Test management buttons
    await expect(page.locator('button:has-text("Refresh")')).toBeVisible();
    await expect(page.locator('button:has-text("Cancel All Pending")')).toBeVisible();
    await expect(page.locator('button:has-text("Clean Up Old Jobs")')).toBeVisible();
    await expect(page.locator('button:has-text("Export")')).toBeVisible();

    // Test status filter dropdown
    const statusFilter = page.locator('#status-filter');
    await expect(statusFilter).toBeVisible();
    
    // Test status filter functionality - use the actual text values
    await statusFilter.selectOption('All Statuses');

    // Verify table structure
    const table = page.locator('table.scheduled-searches-table');
    await expect(table).toBeVisible();

    // Verify table headers
    const headers = ['ID', 'Name', 'Search Term', 'Location', 'Sites', 'Status', 'Scheduled', 'Jobs Found', 'Run Count', 'Actions'];
    for (const header of headers) {
        await expect(table.locator(`th:has-text("${header}")`)).toBeVisible();
    }

    // Verify empty state message
    await expect(page.locator('.empty-state h3')).toContainText('No searches found');
    await expect(page.locator('.empty-state p')).toContainText('Create your first search using the form above.');
  });

  test('should test clear form functionality', async ({ page }) => {
    // Fill out the future search form
    await page.locator('#search-name-input').fill('Test Clear Form');
    await page.locator('#search-term-input').fill('test engineer');
    await page.locator('#location-input').fill('New York');
    await page.locator('#description-input').fill('Test description');

    // Verify form is filled
    await expect(page.locator('#search-name-input')).toHaveValue('Test Clear Form');
    await expect(page.locator('#search-term-input')).toHaveValue('test engineer');
    await expect(page.locator('#location-input')).toHaveValue('New York');
    await expect(page.locator('#description-input')).toHaveValue('Test description');

    // Click clear form button
    await page.locator('button:has-text("Clear Form")').click();

    // Verify form is cleared
    await expect(page.locator('#search-name-input')).toHaveValue('');
    await expect(page.locator('#search-term-input')).toHaveValue('');
    await expect(page.locator('#location-input')).toHaveValue('');
    await expect(page.locator('#description-input')).toHaveValue('');
  });

  test('should handle search management refresh functionality', async ({ page }) => {
    // Test refresh button
    await page.locator('button:has-text("Refresh")').click();
    
    // Verify page doesn't break after refresh
    await expect(page.locator('h2:has-text("Scheduled Searches")')).toBeVisible();
    
    // Test that table is still properly structured
    await expect(page.locator('table.scheduled-searches-table')).toBeVisible();
    await expect(page.locator('table.scheduled-searches-table th:has-text("ID")')).toBeVisible();
  });

  test('should verify navigation links work correctly', async ({ page }) => {
    // Test all navigation links are present and functional
    const navigationLinks = [
      { name: 'Dashboard', url: '/admin/' },
      { name: 'Searches', url: '/admin/searches' },
      { name: 'Scheduler', url: '/admin/scheduler' },
      { name: 'Jobs', url: '/admin/jobs/page' },
      { name: 'Templates', url: '/admin/templates' },
      { name: 'Analytics', url: '/admin/analytics' },
      { name: 'Settings', url: '/admin/settings' }
    ];

    for (const link of navigationLinks) {
      const navLink = page.locator(`#main-nav a[href="${link.url}"]`);
      await expect(navLink).toBeVisible();
    }

    // Test navigation to dashboard and back
    await page.locator('#main-nav a[href="/admin/"]').click();
    await expect(page).toHaveURL('/admin/');
    
    // Navigate back to searches
    await page.locator('#main-nav a[href="/admin/searches"]').click();
    await expect(page).toHaveURL('/admin/searches');
    await expect(page.locator('h1')).toContainText('Search Management');
  });

  test('should test all form validations and interactions', async ({ page }) => {
    // Test that required fields are properly marked
    const scheduleButton = page.locator('button:has-text("Schedule Search")');
    await expect(scheduleButton).toBeVisible();

    // Test job sites multi-select behavior
    const jobSitesListbox = page.locator('#job-sites-select');
    
    // Check default selections
    await expect(jobSitesListbox).toHaveValues(['indeed', 'linkedin']);
    
    // Test that job sites options are available
    await expect(page.locator('#job-sites-select option[value="glassdoor"]')).toBeVisible();
    await expect(page.locator('#job-sites-select option[value="ziprecruiter"]')).toBeVisible();
    await expect(page.locator('#job-sites-select option[value="google"]')).toBeVisible();
    
    // Test results per site boundaries
    const resultsInput = page.locator('#results-per-site-input');
    await resultsInput.fill('100');
    await expect(resultsInput).toHaveValue('100');
    
    await resultsInput.fill('1');
    await expect(resultsInput).toHaveValue('1');
  });
});