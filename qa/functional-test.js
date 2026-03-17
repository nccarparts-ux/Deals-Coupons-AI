const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const ISSUES_PATH = path.join(__dirname, '..', 'issues.jsonl');
const PRODUCTION_URL = 'https://family-nest-auctions.vercel.app';

class FunctionalTester {
  constructor() {
    this.browser = null;
    this.context = null;
    this.page = null;
  }

  async initialize() {
    this.browser = await chromium.launch({ headless: true });
    this.context = await this.browser.newContext({
      viewport: { width: 1280, height: 720 }
    });
    this.page = await this.context.newPage();
  }

  async cleanup() {
    if (this.browser) {
      await this.browser.close();
    }
  }

  async testCriticalFlows() {
    console.log('Testing critical user flows on production site...');
    const issues = [];

    try {
      await this.initialize();

      // Test 1: Homepage loads
      console.log('Test 1: Homepage loads');
      try {
        await this.page.goto(PRODUCTION_URL, { waitUntil: 'networkidle', timeout: 30000 });
        await this.page.waitForSelector('body', { timeout: 10000 });

        // Check for key elements
        const hasHeader = await this.page.locator('header, nav, .hero').first().isVisible().catch(() => false);
        if (!hasHeader) {
          issues.push({ test: 'homepage_load', message: 'Homepage missing key elements (header/nav/hero)' });
        }
      } catch (error) {
        issues.push({ test: 'homepage_load', message: `Homepage failed to load: ${error.message}` });
      }

      // Test 2: Navigation between pages
      console.log('Test 2: Navigation works');
      try {
        // Find and click auction browse link
        const browseLink = this.page.locator('a[href*="auction-browse"]').first();
        if (await browseLink.isVisible({ timeout: 5000 }).catch(() => false)) {
          await browseLink.click();
          await this.page.waitForURL(/auction-browse/, { timeout: 10000 });
          await this.page.waitForSelector('body', { timeout: 5000 });
        } else {
          issues.push({ test: 'navigation', message: 'Auction browse link not found or not visible' });
        }
      } catch (error) {
        issues.push({ test: 'navigation', message: `Navigation failed: ${error.message}` });
      }

      // Test 3: Modal interaction (signup)
      console.log('Test 3: Modal interaction');
      try {
        await this.page.goto(PRODUCTION_URL, { waitUntil: 'networkidle' });

        // Try to open signup modal
        const signupButton = this.page.locator('button:has-text("Start Bidding Free")').first();
        if (await signupButton.isVisible({ timeout: 5000 }).catch(() => false)) {
          await signupButton.click();

          // Wait for modal
          const modalVisible = await this.page.locator('#ov-register, .overlay, [class*="modal"]').first()
            .isVisible({ timeout: 5000 }).catch(() => false);

          if (modalVisible) {
            // Check form elements
            const hasNameInput = await this.page.locator('#reg-name, input[name*="name"]').first()
              .isVisible().catch(() => false);
            const hasEmailInput = await this.page.locator('#reg-email, input[type="email"]').first()
              .isVisible().catch(() => false);

            if (!hasNameInput || !hasEmailInput) {
              issues.push({ test: 'modal_form', message: 'Signup modal missing form fields' });
            }

            // Close modal
            const closeButton = this.page.locator('.modal-x, button:has-text("✕")').first();
            if (await closeButton.isVisible().catch(() => false)) {
              await closeButton.click();
            }
          } else {
            issues.push({ test: 'modal_open', message: 'Signup modal did not open' });
          }
        }
      } catch (error) {
        issues.push({ test: 'modal_interaction', message: `Modal test failed: ${error.message}` });
      }

      // Test 4: Browse page content
      console.log('Test 4: Browse page content');
      try {
        await this.page.goto(`${PRODUCTION_URL}/auction-browse.html`, { waitUntil: 'networkidle', timeout: 30000 });
        await this.page.waitForSelector('body', { timeout: 10000 });

        // Check for content
        const hasContent = await this.page.locator('h1:has-text(/browse|auctions/i), .auction-card, .item-card, [class*="item"]').first()
          .isVisible({ timeout: 5000 }).catch(() => false);

        const hasNoContentMsg = await this.page.locator('text=/no.*items|empty|no.*results/i').first()
          .isVisible({ timeout: 2000 }).catch(() => false);

        if (!hasContent && !hasNoContentMsg) {
          issues.push({ test: 'browse_content', message: 'Browse page has no content or messages' });
        }
      } catch (error) {
        issues.push({ test: 'browse_page', message: `Browse page failed: ${error.message}` });
      }

      // Test 5: Authentication pages (should redirect when not logged in)
      console.log('Test 5: Authentication redirects');
      const authPages = [
        { path: '/account-dashboard.html', name: 'Account dashboard' },
        { path: '/seller-dashboard.html', name: 'Seller dashboard' },
        { path: '/admin-panel.html', name: 'Admin panel' }
      ];

      for (const pageInfo of authPages) {
        try {
          await this.page.goto(`${PRODUCTION_URL}${pageInfo.path}`, { waitUntil: 'domcontentloaded', timeout: 15000 });
          await this.page.waitForTimeout(1000);

          // Check if redirected to main page (not logged in)
          const currentUrl = this.page.url();
          const isRedirected = !currentUrl.includes(pageInfo.path) || currentUrl.includes('index.html');

          if (!isRedirected) {
            // Might be logged in or page doesn't require auth
            const requiresAuth = await this.page.locator('text=/sign.*in|log.*in|not.*authorized/i').isVisible().catch(() => false);
            if (requiresAuth) {
              issues.push({ test: 'auth_redirect', message: `${pageInfo.name} should redirect when not authenticated` });
            }
          }
        } catch (error) {
          // Timeout or error - might be expected
          console.log(`Auth test for ${pageInfo.name}: ${error.message}`);
        }
      }

    } catch (error) {
      console.error('Functional test suite failed:', error);
      issues.push({ test: 'test_suite', message: `Test suite error: ${error.message}` });
    } finally {
      await this.cleanup();
    }

    // Log issues
    issues.forEach(issue => this.logIssue('functional_test', PRODUCTION_URL, `${issue.test}: ${issue.message}`));

    console.log(`Functional testing complete. Found ${issues.length} issues.`);
    return issues;
  }

  async testRegistrationFlow() {
    console.log('Testing registration flow...');
    const testEmail = `test-${Date.now()}@bidyard-qa.com`;
    const testPassword = 'TestPassword123!';
    const testName = 'QA Test User';

    try {
      await this.initialize();
      await this.page.goto(PRODUCTION_URL, { waitUntil: 'networkidle' });

      // Open signup modal
      const signupButton = this.page.locator('button:has-text("Start Bidding Free")').first();
      if (!await signupButton.isVisible({ timeout: 5000 }).catch(() => false)) {
        return { success: false, message: 'Signup button not visible' };
      }

      await signupButton.click();

      // Wait for modal
      await this.page.waitForSelector('#ov-register, .overlay', { state: 'visible', timeout: 5000 });

      // Fill form
      await this.page.fill('#reg-name, input[name*="name"]', testName);
      await this.page.fill('#reg-email, input[type="email"]', testEmail);
      await this.page.fill('#reg-password, input[type="password"]', testPassword);

      // Submit
      await this.page.click('#reg-btn, button:has-text("Create Free Account")');

      // Wait for response
      await this.page.waitForTimeout(3000);

      // Check for success (redirect, logged in state, or success message)
      const successIndicators = [
        () => this.page.locator('text=/welcome|success|account.*created/i').isVisible(),
        () => this.page.locator('a[href*="account-dashboard"]').isVisible(),
        () => !this.page.url().includes(PRODUCTION_URL) // redirected
      ];

      let success = false;
      for (const indicator of successIndicators) {
        if (await indicator().catch(() => false)) {
          success = true;
          break;
        }
      }

      return { success, message: success ? 'Registration successful' : 'Registration may have failed' };

    } catch (error) {
      return { success: false, message: `Registration error: ${error.message}` };
    } finally {
      await this.cleanup();
    }
  }

  logIssue(type, url, message) {
    const issue = {
      id: `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      type,
      url,
      message,
      timestamp: new Date().toISOString()
    };
    fs.appendFileSync(ISSUES_PATH, JSON.stringify(issue) + '\n');
    console.log(`Logged functional issue: ${message}`);
  }

  async runFullSuite() {
    console.log('=== Running Functional Test Suite ===');
    const results = {
      criticalFlows: [],
      registration: null
    };

    results.criticalFlows = await this.testCriticalFlows();

    // Only test registration if critical flows pass
    if (results.criticalFlows.length === 0) {
      results.registration = await this.testRegistrationFlow();
      if (!results.registration.success) {
        this.logIssue('functional_test', PRODUCTION_URL, `Registration flow: ${results.registration.message}`);
      }
    }

    console.log('=== Functional Test Suite Complete ===');
    return results;
  }
}

// Run if called directly
if (require.main === module) {
  const tester = new FunctionalTester();
  tester.runFullSuite().catch(console.error);
}

module.exports = FunctionalTester;