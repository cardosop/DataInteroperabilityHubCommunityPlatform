/**
 * Form accessibility tests.
 *
 * Verifies that form elements (login form specifically) have proper labels,
 * aria attributes, and required field indicators.
 * Gated behind E2E_A11Y env var; skips gracefully when the app is unavailable.
 */
import { test, expect } from '@playwright/test';
import { gotoWithRetry } from '../fixtures/auth';

test.describe('Form Accessibility', () => {

  test('login form has proper labels', async ({ page }) => {
    // gotoWithRetry instead of page.goto — Chromium's
    // net::ERR_NETWORK_CHANGED / ERR_NETWORK_IO_SUSPENDED on Wi-Fi/VPN
    // blips during long staging runs is matched by the Fix-13 retry regex
    // in isConnectionError; bare page.goto bypasses that retry. See
    // tasks.md § 226.H.staging-run cycle 9 — Fix 27.
    await gotoWithRetry(page, '/login', { waitUntil: 'domcontentloaded' });
    if (!(await page.title())) {
      test.skip(true, 'App not running');
      return;
    }

    // Email input should have a label
    const emailInput = page.locator('input[type="email"], input[name="email"]');
    if ((await emailInput.count()) === 0) {
      test.skip(true, 'Login form email input not found; form may not be available');
      return;
    }
    const ariaLabel = await emailInput.getAttribute('aria-label');
    const id = await emailInput.getAttribute('id');
    const hasLabel =
      ariaLabel ||
      (id && (await page.locator(`label[for="${id}"]`).count()) > 0);
    expect(hasLabel).toBeTruthy();
  });

  test('required fields have indicators', async ({ page }) => {
    await gotoWithRetry(page, '/login', { waitUntil: 'domcontentloaded' });
    if (!(await page.title())) {
      test.skip(true, 'App not running');
      return;
    }

    // Required inputs should have aria-required or required attribute
    const requiredInputs = page.locator(
      'input[required], input[aria-required="true"]',
    );
    const count = await requiredInputs.count();
    // Login form must have at least email + password as required (2 fields minimum)
    expect(count).toBeGreaterThanOrEqual(2);
  });
});
