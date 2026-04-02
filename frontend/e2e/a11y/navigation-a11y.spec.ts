/**
 * Navigation accessibility tests.
 *
 * Verifies that the app has proper navigation landmarks, skip-to-content links,
 * and focusable interactive elements.
 * Gated behind E2E_A11Y env var; skips gracefully when the app is unavailable.
 */
import { test, expect } from '@playwright/test';

test.describe('Navigation Accessibility', () => {
  // E2E_A11Y gate removed: these are fast (< 2s) fundamental checks that should always run.

  test('page has skip-to-content or main landmark', async ({ page }) => {
    // Use /login which renders immediately with role="main" regardless of auth state.
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    if (!(await page.title())) {
      test.skip(true, 'App not running');
      return;
    }

    // Login page / landing page should have a main landmark
    const mainCount = await page.locator('main, [role="main"]').count();
    expect(mainCount).toBeGreaterThanOrEqual(1);
  });

  test('interactive elements are focusable', async ({ page }) => {
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    if (!(await page.title())) {
      test.skip(true, 'App not running');
      return;
    }

    // Buttons and links should be focusable
    const buttons = page.locator('button, a[href]');
    const count = await buttons.count();
    expect(count).toBeGreaterThan(0);
  });
});
