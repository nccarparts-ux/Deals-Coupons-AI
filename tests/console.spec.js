const { test, expect } = require('@playwright/test');

test('no JavaScript errors on homepage', async ({ page }) => {
  const errors = [];
  const consoleMessages = [];

  // Capture console errors
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleMessages.push(`Console error: ${msg.text()}`);
    }
  });

  // Capture page errors (uncaught exceptions)
  page.on('pageerror', error => {
    errors.push(`Page error: ${error.message}`);
  });

  await page.goto('/index.html', { waitUntil: 'networkidle' });

  // Wait a bit for any async errors
  await page.waitForTimeout(1000);

  // Check for undefined variable errors (common after rebranding)
  const undefinedErrors = [...errors, ...consoleMessages].filter(msg =>
    msg.includes('is not defined') || msg.includes('undefined')
  );

  expect(undefinedErrors, `Found undefined variable errors: ${JSON.stringify(undefinedErrors)}`).toHaveLength(0);

  // Log any errors for debugging
  if (errors.length > 0 || consoleMessages.length > 0) {
    console.log('Errors found:', errors);
    console.log('Console messages:', consoleMessages);
  }
});

test('modal opens without errors', async ({ page }) => {
  const errors = [];
  const consoleMessages = [];

  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleMessages.push(`Console error: ${msg.text()}`);
    }
  });

  page.on('pageerror', error => {
    errors.push(`Page error: ${error.message}`);
  });

  await page.goto('/index.html', { waitUntil: 'networkidle' });

  // Try to open a modal if there is one (adjust selector as needed)
  const modalButton = page.locator('[data-modal-open], .modal-open, button:has-text("Open Modal")').first();
  if (await modalButton.count() > 0) {
    await modalButton.click();
    await page.waitForTimeout(500);
  }

  const undefinedErrors = [...errors, ...consoleMessages].filter(msg =>
    msg.includes('is not defined') || msg.includes('undefined')
  );

  expect(undefinedErrors, `Found undefined variable errors when opening modal: ${JSON.stringify(undefinedErrors)}`).toHaveLength(0);
});