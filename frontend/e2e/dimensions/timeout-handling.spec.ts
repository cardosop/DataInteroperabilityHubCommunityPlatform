/**
 * Dimension: Timeout handling
 * Cross-cutting E2E for long-running operations and retry behavior.
 * Per tasks 8.7.2: frontend/e2e/dimensions/timeout-handling.spec.ts
 * Run: npm run test:e2e -- e2e/dimensions/timeout-handling.spec.ts
 *
 * No mocks; real backend. Tests assert that slow or delayed responses
 * are handled (loading state, eventual success or timeout error).
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Dimension: Timeout handling', () => {
  test.setTimeout(90000);

  test('login with slow API response eventually completes or shows error', async ({ page }) => {
    await clearAuthStorage(page);
    let delayCount = 0;
    await page.route('**/api/v1/auth/login/**', async (route) => {
      delayCount++;
      if (delayCount <= 1) {
        await new Promise((r) => setTimeout(r, 2000));
      }
      await route.continue();
    });
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    const testUser = await getTestUser();
    await page.fill('input#email', testUser.email);
    await page.fill('input#password', testUser.password);
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(8000);
    const leftLogin = !page.url().includes('/login');
    const hasError = (await page.locator('.error-message').count()) > 0;
    expect(leftLogin || hasError).toBe(true);
  });

  test('assets list load completes within reasonable time or shows loading then content', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, .empty-state, .error-display, .loading-spinner-container',
    });
    await page.waitForTimeout(2000);
    const hasContent =
      (await page.locator('.asset-list-page').count()) > 0 ||
      (await page.locator('.empty-state').count()) > 0 ||
      (await page.locator('.error-display').count()) > 0;
    expect(hasContent).toBe(true);
  });
});
