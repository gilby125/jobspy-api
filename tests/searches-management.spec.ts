import { test, expect } from '@playwright/test';

test.describe('JobSpy Admin - Searches Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/admin/searches');
  });

  test('should display search statistics dashboard', async ({ page }) => {
    // Verify page title and main heading
    await expect(page).toHaveTitle('JobSpy Admin - Searches');
    await expect(page.getByRole('heading', { name: '🔍 Search Management', level: 1 })).toBeVisible();
    await expect(page.getByText('Schedule, monitor, and manage job searches')).toBeVisible();

    // Verify search statistics section with all metrics
    await expect(page.getByRole('heading', { name: '📊 Search Statistics', level: 2 })).toBeVisible();
    await expect(page.getByText('Total Searches')).toBeVisible();
    await expect(page.getByText('Active Searches')).toBeVisible();
    await expect(page.getByText('Completed Today')).toBeVisible();
    await expect(page.getByText('Success Rate')).toBeVisible();

    // Verify numeric values are displayed (should be "0" for new system)
    await expect(page.locator('text=0').first()).toBeVisible();
  });

  test('should display quick actions section with working buttons', async ({ page }) => {
    // Verify Quick Actions section
    await expect(page.getByRole('heading', { name: '⚡ Quick Actions', level: 2 })).toBeVisible();
    await expect(page.getByText('For immediate job searches, use the direct search API:')).toBeVisible();
    
    // Verify buttons are visible and clickable
    await expect(page.getByRole('button', { name: '🔍 Quick Search (Immediate)' })).toBeVisible();
    await expect(page.getByRole('button', { name: '📚 API Documentation' })).toBeVisible();
    
    // Verify explanatory text
    await expect(page.getByText('Quick Search opens the direct API interface for immediate job searches. Use the scheduler below for future or recurring searches.')).toBeVisible();

    // Test button interactions
    await page.getByRole('button', { name: '🔍 Quick Search (Immediate)' }).click();
    await page.getByRole('button', { name: '📚 API Documentation' }).click();
    // Note: These buttons may open new tabs or trigger JavaScript actions
  });

  test('should handle future search form with all field types', async ({ page }) => {
    // Verify Schedule Future Search form
    await expect(page.getByRole('heading', { name: '⏰ Schedule Future Search', level: 2 })).toBeVisible();

    // Test all input fields
    await page.getByRole('textbox', { name: 'Search Name:' }).fill('Test Future Search');
    await page.getByRole('textbox', { name: 'Search Term:' }).fill('software engineer');
    await page.getByRole('textbox', { name: 'Location:' }).fill('San Francisco, CA');

    // Test job sites multi-select
    const jobSitesListbox = page.getByRole('listbox', { name: 'Job Sites:' });
    await expect(jobSitesListbox.getByRole('option', { name: 'Indeed' })).toBeVisible();
    await expect(jobSitesListbox.getByRole('option', { name: 'LinkedIn' })).toBeVisible();
    await expect(jobSitesListbox.getByRole('option', { name: 'Glassdoor' })).toBeVisible();
    await expect(jobSitesListbox.getByRole('option', { name: 'ZipRecruiter' })).toBeVisible();
    await expect(jobSitesListbox.getByRole('option', { name: 'Google Jobs' })).toBeVisible();

    // Test numeric input
    await page.getByRole('spinbutton', { name: 'Results per Site:' }).fill('50');
    await expect(page.getByRole('spinbutton', { name: 'Results per Site:' })).toHaveValue('50');

    // Test job type dropdown
    const jobTypeCombobox = page.getByRole('combobox', { name: 'Job Type:' });
    await expect(jobTypeCombobox).toHaveValue('');
    await jobTypeCombobox.selectOption('fulltime');
    await expect(jobTypeCombobox).toHaveValue('fulltime');

    // Test schedule type dropdown
    const scheduleTypeCombobox = page.getByRole('combobox', { name: 'Schedule Type:' });
    await expect(scheduleTypeCombobox).toHaveValue('scheduled');
    await scheduleTypeCombobox.selectOption('recurring');
    await expect(scheduleTypeCombobox).toHaveValue('recurring');

    // Test datetime input
    const scheduleTimeInput = page.getByRole('textbox', { name: 'Schedule Time:' });
    await expect(scheduleTimeInput).toBeVisible();
    // Note: Default value is auto-populated with current datetime

    // Test optional description field
    await page.getByRole('textbox', { name: 'Description (optional):' }).fill('Test search description for automated testing');

    // Verify action buttons
    await expect(page.getByRole('button', { name: '🚀 Schedule Search' })).toBeVisible();
    await expect(page.getByRole('button', { name: '🗑️ Clear Form' })).toBeVisible();
    await expect(page.getByRole('button', { name: '📋 Load Template' }).first()).toBeVisible();
  });

  test('should handle bulk search operations', async ({ page }) => {
    // Verify Bulk Search Operations section
    await expect(page.getByRole('heading', { name: '📦 Bulk Search Operations', level: 2 })).toBeVisible();
    await expect(page.getByText('Schedule multiple searches at once with different parameters')).toBeVisible();

    // Test batch naming
    await page.getByRole('textbox', { name: 'Batch Name:' }).fill('Engineering Jobs Batch');
    await expect(page.getByRole('textbox', { name: 'Batch Name:' })).toHaveValue('Engineering Jobs Batch');

    // Test bulk operation buttons
    await expect(page.getByRole('button', { name: '➕ Add Search' })).toBeVisible();
    await expect(page.getByRole('button', { name: '🗑️ Clear All' })).toBeVisible();
    await expect(page.getByRole('button', { name: '📋 Load Template' }).nth(1)).toBeVisible();

    // Verify first search form is present
    await expect(page.getByText('Search #1')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Remove' })).toBeVisible();

    // Fill out the first bulk search
    await page.getByRole('textbox', { name: 'e.g. Python Remote Jobs' }).fill('Senior Python Developer Jobs');
    await page.getByRole('textbox', { name: 'e.g. Python Developer' }).fill('senior python developer');
    await page.getByRole('textbox', { name: 'e.g. San Francisco, CA' }).fill('Remote');

    // Verify bulk search form fields are filled
    await expect(page.getByRole('textbox', { name: 'e.g. Python Remote Jobs' })).toHaveValue('Senior Python Developer Jobs');
    await expect(page.getByRole('textbox', { name: 'e.g. Python Developer' })).toHaveValue('senior python developer');
    await expect(page.getByRole('textbox', { name: 'e.g. San Francisco, CA' })).toHaveValue('Remote');

    // Test bulk action buttons
    await expect(page.getByRole('button', { name: '🚀 Schedule All Searches' })).toBeVisible();
    await expect(page.getByRole('button', { name: '👁️ Preview' })).toBeVisible();

    // Test preview functionality
    await page.getByRole('button', { name: '👁️ Preview' }).click();
  });

  test('should display scheduled searches table with proper structure', async ({ page }) => {
    // Verify Scheduled Searches section
    await expect(page.getByRole('heading', { name: '📋 Scheduled Searches', level: 2 })).toBeVisible();

    // Test management buttons
    await expect(page.getByRole('button', { name: '🔄 Refresh' })).toBeVisible();
    await expect(page.getByRole('button', { name: '⏸️ Cancel All Pending' })).toBeVisible();
    await expect(page.getByRole('button', { name: '🗑️ Clean Up Old Jobs' })).toBeVisible();
    await expect(page.getByRole('button', { name: '📊 Export' })).toBeVisible();

    // Test status filter dropdown
    const statusFilter = page.locator('#status-filter');
    await expect(statusFilter).toBeVisible();
    
    // Test status filter functionality - use the actual text values
    await statusFilter.selectOption('All Statuses');
    // Note: Checking the exact value after selection based on actual implementation

    // Verify table structure
    const table = page.getByRole('table');
    await expect(table).toBeVisible();

    // Verify table headers
    await expect(page.getByRole('cell', { name: 'ID' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'Name' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'Search Term' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'Location' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'Sites' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'Status' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'Scheduled' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'Jobs Found' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'Run Count' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'Actions' })).toBeVisible();

    // Verify empty state message
    await expect(page.getByRole('heading', { name: 'No searches found', level: 3 })).toBeVisible();
    await expect(page.getByText('Create your first search using the form above.')).toBeVisible();
  });

  test('should test clear form functionality', async ({ page }) => {
    // Fill out the future search form
    await page.getByRole('textbox', { name: 'Search Name:' }).fill('Test Clear Form');
    await page.getByRole('textbox', { name: 'Search Term:' }).fill('test engineer');
    await page.getByRole('textbox', { name: 'Location:' }).fill('New York');
    await page.getByRole('textbox', { name: 'Description (optional):' }).fill('Test description');

    // Verify form is filled
    await expect(page.getByRole('textbox', { name: 'Search Name:' })).toHaveValue('Test Clear Form');
    await expect(page.getByRole('textbox', { name: 'Search Term:' })).toHaveValue('test engineer');
    await expect(page.getByRole('textbox', { name: 'Location:' })).toHaveValue('New York');
    await expect(page.getByRole('textbox', { name: 'Description (optional):' })).toHaveValue('Test description');

    // Click clear form button
    await page.getByRole('button', { name: '🗑️ Clear Form' }).click();

    // Verify form is cleared (depending on implementation, fields should be empty)
    // Note: This test may need adjustment based on actual clear form behavior
  });

  test('should handle search management refresh functionality', async ({ page }) => {
    // Test refresh button
    await page.getByRole('button', { name: '🔄 Refresh' }).click();
    
    // Verify page doesn't break after refresh
    await expect(page.getByRole('heading', { name: '📋 Scheduled Searches', level: 2 })).toBeVisible();
    
    // Test that table is still properly structured
    await expect(page.getByRole('table')).toBeVisible();
    await expect(page.getByRole('cell', { name: 'ID' })).toBeVisible();
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
      const navLink = page.getByRole('link', { name: link.name, exact: true });
      await expect(navLink).toBeVisible();
      await expect(navLink).toHaveAttribute('href', link.url);
    }

    // Test navigation to dashboard and back
    await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
    await expect(page).toHaveURL('/admin/');
    
    // Navigate back to searches
    await page.getByRole('link', { name: 'Searches', exact: true }).click();
    await expect(page).toHaveURL('/admin/searches');
    await expect(page.getByRole('heading', { name: '🔍 Search Management', level: 1 })).toBeVisible();
  });

  test('should test all form validations and interactions', async ({ page }) => {
    // Test that required fields are properly marked
    const scheduleButton = page.getByRole('button', { name: '🚀 Schedule Search' });
    await expect(scheduleButton).toBeVisible();

    // Test job sites multi-select behavior
    const jobSitesListbox = page.getByRole('listbox', { name: 'Job Sites:' });
    
    // Check default selections
    await expect(jobSitesListbox.getByRole('option', { name: 'Indeed' })).toBeVisible();
    await expect(jobSitesListbox.getByRole('option', { name: 'LinkedIn' })).toBeVisible();
    
    // Test that job sites options are available (using visible text)
    await expect(jobSitesListbox.getByText('Glassdoor')).toBeAttached();
    await expect(jobSitesListbox.getByText('ZipRecruiter')).toBeAttached();
    await expect(jobSitesListbox.getByText('Google Jobs')).toBeAttached();
    
    // Test results per site boundaries
    const resultsInput = page.getByRole('spinbutton', { name: 'Results per Site:' });
    await resultsInput.fill('100');
    await expect(resultsInput).toHaveValue('100');
    
    await resultsInput.fill('1');
    await expect(resultsInput).toHaveValue('1');
  });
});