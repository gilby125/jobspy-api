import { test, expect } from '@playwright/test';

test.describe('JobSpy Admin Interface', () => {
  test('should display admin dashboard with all navigation elements', async ({ page }) => {
    // Navigate to admin dashboard
    await page.goto('http://192.168.7.10:8787/admin/');

    // Verify page title and main heading
    await expect(page).toHaveTitle('JobSpy Admin Panel');
    await expect(page.getByRole('heading', { name: '🔧 JobSpy Admin Panel', level: 1 })).toBeVisible();

    // Verify navigation links are present (using exact matches to avoid strict mode violations)
    await expect(page.getByRole('link', { name: 'Dashboard', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Searches', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Scheduler', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Jobs', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Templates', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Analytics', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Settings', exact: true })).toBeVisible();

    // Verify quick stats section
    await expect(page.getByRole('heading', { name: '📊 Quick Stats', level: 2 })).toBeVisible();
    await expect(page.getByText('Total Searches')).toBeVisible();
    await expect(page.getByText('Jobs Found Today')).toBeVisible();
    await expect(page.getByText('Active Searches')).toBeVisible();
    await expect(page.getByText('System Health', { exact: true })).toBeVisible();

    // Verify quick actions section
    await expect(page.getByRole('heading', { name: '🚀 Quick Actions', level: 2 })).toBeVisible();
    await expect(page.getByRole('link', { name: /📋 Manage Searches/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /⚙️ Scheduler/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /💼 Jobs Database/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /📄 Search Templates/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /📈 Analytics/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /🔧 System Settings/ })).toBeVisible();
  });

  test('should allow filling out job search form', async ({ page }) => {
    // Navigate to admin dashboard
    await page.goto('http://192.168.7.10:8787/admin/');

    // Verify quick search form is visible
    await expect(page.getByRole('heading', { name: '🔍 Quick Search', level: 2 })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Schedule New Job Search', level: 3 })).toBeVisible();

    // Fill out the search form using more specific selectors to avoid conflicts
    await page.getByRole('textbox', { name: 'e.g., Software Engineers SF', exact: true }).fill('Test Search Senior Developer');
    await page.getByRole('textbox', { name: 'e.g., software engineer', exact: true }).fill('senior developer');
    await page.getByRole('textbox', { name: 'e.g., San Francisco, CA', exact: true }).fill('New York, NY');

    // Verify form fields are filled correctly
    await expect(page.getByRole('textbox', { name: 'e.g., Software Engineers SF', exact: true })).toHaveValue('Test Search Senior Developer');
    await expect(page.getByRole('textbox', { name: 'e.g., software engineer', exact: true })).toHaveValue('senior developer');
    await expect(page.getByRole('textbox', { name: 'e.g., San Francisco, CA', exact: true })).toHaveValue('New York, NY');

    // Verify job sites selection (Indeed and LinkedIn should be pre-selected)
    const jobSitesListbox = page.getByRole('listbox');
    await expect(jobSitesListbox.getByRole('option', { name: 'Indeed (Recommended)' })).toBeVisible();
    await expect(jobSitesListbox.getByRole('option', { name: 'LinkedIn (Recommended)' })).toBeVisible();

    // Verify results per site spinner has default value
    await expect(page.getByRole('spinbutton')).toHaveValue('50');

    // Verify recurring search checkbox is available
    await expect(page.getByRole('checkbox', { name: 'Make this a recurring search' })).toBeVisible();

    // Verify schedule search button is present
    await expect(page.getByRole('button', { name: '📅 Schedule Search' })).toBeVisible();
  });

  test('should navigate to searches management page', async ({ page }) => {
    // Navigate to searches page
    await page.goto('http://192.168.7.10:8787/admin/searches');

    // Verify page title and heading
    await expect(page).toHaveTitle('JobSpy Admin - Searches');
    await expect(page.getByRole('heading', { name: '🔍 Search Management', level: 1 })).toBeVisible();

    // Verify search statistics section
    await expect(page.getByRole('heading', { name: '📊 Search Statistics', level: 2 })).toBeVisible();
    await expect(page.getByText('Total Searches')).toBeVisible();
    await expect(page.getByText('Active Searches')).toBeVisible();
    await expect(page.getByText('Completed Today')).toBeVisible();
    await expect(page.getByText('Success Rate')).toBeVisible();

    // Verify quick actions section
    await expect(page.getByRole('heading', { name: '⚡ Quick Actions', level: 2 })).toBeVisible();
    await expect(page.getByRole('button', { name: '🔍 Quick Search (Immediate)' })).toBeVisible();
    await expect(page.getByRole('button', { name: '📚 API Documentation' })).toBeVisible();

    // Verify schedule future search form
    await expect(page.getByRole('heading', { name: '⏰ Schedule Future Search', level: 2 })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Search Name:' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Search Term:' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Location:' })).toBeVisible();
    await expect(page.getByRole('listbox', { name: 'Job Sites:' })).toBeVisible();
    await expect(page.getByRole('spinbutton', { name: 'Results per Site:' })).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Job Type:' })).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Schedule Type:' })).toBeVisible();
    await expect(page.getByRole('button', { name: '🚀 Schedule Search' })).toBeVisible();

    // Verify bulk search operations section
    await expect(page.getByRole('heading', { name: '📦 Bulk Search Operations', level: 2 })).toBeVisible();
    await expect(page.getByRole('button', { name: '➕ Add Search' })).toBeVisible();
    await expect(page.getByRole('button', { name: '🗑️ Clear All' })).toBeVisible();
    await expect(page.getByRole('button', { name: '📋 Load Template' }).first()).toBeVisible();

    // Verify scheduled searches section
    await expect(page.getByRole('heading', { name: '📋 Scheduled Searches', level: 2 })).toBeVisible();
    await expect(page.getByRole('button', { name: '🔄 Refresh' })).toBeVisible();
    await expect(page.getByRole('button', { name: '⏸️ Cancel All Pending' })).toBeVisible();
    await expect(page.getByRole('button', { name: '🗑️ Clean Up Old Jobs' })).toBeVisible();
    await expect(page.getByRole('button', { name: '📊 Export' })).toBeVisible();

    // Verify the searches table with proper headers
    await expect(page.getByRole('table')).toBeVisible();
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

  test('should fill out future search form with all fields', async ({ page }) => {
    // Navigate to searches page
    await page.goto('http://192.168.7.10:8787/admin/searches');

    // Fill out the future search form
    await page.getByRole('textbox', { name: 'Search Name:' }).fill('Future Test Search');
    await page.getByRole('textbox', { name: 'Search Term:' }).fill('javascript developer');
    await page.getByRole('textbox', { name: 'Location:' }).fill('Remote');

    // Select job type from dropdown
    await page.getByRole('combobox', { name: 'Job Type:' }).selectOption('fulltime');

    // Change results per site
    await page.getByRole('spinbutton', { name: 'Results per Site:' }).fill('30');

    // Verify form fields are filled correctly
    await expect(page.getByRole('textbox', { name: 'Search Name:' })).toHaveValue('Future Test Search');
    await expect(page.getByRole('textbox', { name: 'Search Term:' })).toHaveValue('javascript developer');
    await expect(page.getByRole('textbox', { name: 'Location:' })).toHaveValue('Remote');
    await expect(page.getByRole('combobox', { name: 'Job Type:' })).toHaveValue('fulltime');
    await expect(page.getByRole('spinbutton', { name: 'Results per Site:' })).toHaveValue('30');

    // Verify schedule type options
    const scheduleTypeCombobox = page.getByRole('combobox', { name: 'Schedule Type:' });
    await expect(scheduleTypeCombobox).toHaveValue('scheduled');
    
    // Test changing to recurring
    await scheduleTypeCombobox.selectOption('recurring');
    await expect(scheduleTypeCombobox).toHaveValue('recurring');

    // Verify job sites are pre-selected
    const jobSitesListbox = page.getByRole('listbox', { name: 'Job Sites:' });
    await expect(jobSitesListbox.getByRole('option', { name: 'Indeed' })).toBeVisible();
    await expect(jobSitesListbox.getByRole('option', { name: 'LinkedIn' })).toBeVisible();
  });
});