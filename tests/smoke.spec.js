const { test, expect } = require('@playwright/test');

test('smoke test - server is running', async ({ page }) => {
  // Just check that we can load a page
  await page.goto('http://localhost:3000/index.html');
  console.log('Page URL:', page.url());
  console.log('Page title:', await page.title());

  // Basic check that page loaded
  await expect(page).toHaveTitle(/Deals-Coupons-AI/);
});

test('check index.html loads', async ({ page }) => {
  await page.goto('http://localhost:3000/');
  console.log('Redirected to:', page.url());
  // Should load some page (may redirect via meta refresh)
  await expect(page.locator('body')).toBeVisible();
});