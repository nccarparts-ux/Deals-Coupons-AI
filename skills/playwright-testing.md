# Playwright Testing Skills & Cheat Sheet

## Installation & Setup

### Basic Setup
```bash
# Install Playwright in your project
npm install --save-dev @playwright/test

# Install browser binaries
npx playwright install

# Install specific browsers
npx playwright install chromium firefox webkit
```

### Configuration
Create `playwright.config.js` with:
```javascript
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 30 * 1000,
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
});
```

## Writing Tests

### Basic Test Structure
```javascript
const { test, expect } = require('@playwright/test');

test('page loads successfully', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Your App/);
});

test('user can login', async ({ page }) => {
  await page.goto('/login');
  await page.fill('#email', 'user@example.com');
  await page.fill('#password', 'password123');
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL(/dashboard/);
});
```

### Locators & Assertions
```javascript
// Text-based locators
await page.getByText('Submit').click();
await page.getByLabel('Username').fill('john');
await page.getByPlaceholder('Enter email').fill('test@example.com');
await page.getByRole('button', { name: 'Submit' }).click();

// CSS/XPath locators
await page.locator('.submit-button').click();
await page.locator('//button[contains(text(), "Submit")]').click();

// Assertions
await expect(page).toHaveURL(/dashboard/);
await expect(page.locator('.success-message')).toBeVisible();
await expect(page.locator('.item-count')).toHaveText('10 items');
await expect(page.locator('.checkbox')).toBeChecked();
```

### Page Object Model
```javascript
// models/LoginPage.js
class LoginPage {
  constructor(page) {
    this.page = page;
    this.emailInput = page.locator('#email');
    this.passwordInput = page.locator('#password');
    this.submitButton = page.locator('button[type="submit"]');
  }

  async goto() {
    await this.page.goto('/login');
  }

  async login(email, password) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }
}

// tests/login.spec.js
const { test, expect } = require('@playwright/test');
const LoginPage = require('../models/LoginPage');

test('user login', async ({ page }) => {
  const loginPage = new LoginPage(page);
  await loginPage.goto();
  await loginPage.login('user@example.com', 'password123');
  await expect(page).toHaveURL(/dashboard/);
});
```

## Running Tests

### Basic Commands
```bash
# Run all tests
npx playwright test

# Run tests in UI mode
npx playwright test --ui

# Run tests in debug mode
npx playwright test --debug

# Run tests in headed browsers
npx playwright test --headed

# Run specific test file
npx playwright test tests/login.spec.js

# Run tests matching a pattern
npx playwright test --grep "login"
```

### CI/CD Integration
```bash
# Install browsers for CI
npx playwright install --with-deps

# Run tests with CI settings
npx playwright test --reporter=line

# Generate HTML report
npx playwright show-report
```

## Advanced Features

### Fixtures & Hooks
```javascript
const { test, expect } = require('@playwright/test');

test.beforeEach(async ({ page }) => {
  await page.goto('/');
});

test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status !== 'passed') {
    await page.screenshot({ path: `screenshots/${testInfo.title}.png` });
  }
});

test.describe('authentication', () => {
  test('user can login', async ({ page }) => {
    // Test code
  });

  test('user can logout', async ({ page }) => {
    // Test code
  });
});
```

### Handling Authentication
```javascript
// Global setup for authenticated state
const { test, expect } = require('@playwright/test');

test.use({
  storageState: 'playwright/.auth/user.json',
});

test('authenticated user sees dashboard', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page.locator('.welcome-message')).toBeVisible();
});
```

### API Testing
```javascript
const { test, expect } = require('@playwright/test');

test('API endpoint returns data', async ({ request }) => {
  const response = await request.get('/api/items');
  expect(response.ok()).toBeTruthy();

  const items = await response.json();
  expect(items.length).toBeGreaterThan(0);
});

test('POST request works', async ({ request }) => {
  const response = await request.post('/api/items', {
    data: { title: 'New Item', price: 99.99 }
  });
  expect(response.status()).toBe(201);
});
```

## Deals-Coupons-AI Test Examples

### Page Load Tests
```javascript
test('main page loads', async ({ page }) => {
  await page.goto('/index.html');
  await expect(page).toHaveTitle(/Deals-Coupons-AI/);
  await expect(page.locator('.hero h1')).toBeVisible();
});

test('admin panel accessible', async ({ page }) => {
  await page.goto('/admin-panel.html');
  await expect(page).toHaveTitle(/Admin Panel/);
  await expect(page.locator('.admin-badge')).toBeVisible();
});
```

### Form Interaction Tests
```javascript
test('user can search items', async ({ page }) => {
  await page.goto('/index.html');
  await page.fill('.search-bar input', 'search term');
  await page.selectOption('.search-bar select', 'category');
  await page.click('.btn-search');
  await expect(page.locator('.results-container')).toBeVisible();
});
```

### API Integration Tests
```javascript
test('Supabase API returns items', async ({ request }) => {
  const response = await request.get('/api/items');
  expect(response.ok()).toBeTruthy();

  const items = await response.json();
  expect(Array.isArray(items)).toBeTruthy();
});
```

## Best Practices

### Test Organization
1. Group related tests with `test.describe()`
2. Use page object model for complex pages
3. Store test data in fixtures or JSON files
4. Use meaningful test names that describe behavior

### Performance Tips
1. Run tests in parallel with `fullyParallel: true`
2. Use `test.setTimeout()` for long-running tests
3. Reuse authentication state with `storageState`
4. Clean up test data in `afterEach` hooks

### CI/CD Pipeline
```yaml
# GitHub Actions example
name: Playwright Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm ci
      - run: npx playwright install --with-deps
      - run: npx playwright test
      - uses: actions/upload-artifact@v3
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 30
```