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
import { clearAuthStorage, getTestUser, gotoWithRetry } from '../fixtures/auth';
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
    // Raw page.goto uses the global navigationTimeout (30s) with no retry. Staging
    // occasionally exceeds that for the first HTML navigation under load; the failure
    // in front-staging.log was TimeoutError on goto, not on the intentional login delay.
    // gotoWithRetry matches auth-storage / loginUser and retries navigation timeouts.
    await gotoWithRetry(page, '/login', { waitUntil: 'domcontentloaded' });
    const testUser = await getTestUser();
    await page.fill('input#email', testUser.email);
    await page.fill('input#password', testUser.password);
    await page.locator('button[type="submit"]').click();
    // Wait for a definitive outcome: either navigate away from /login
    // (success) or show an error message (invalid creds, rate limit, etc.).
    // A fixed timeout (the previous 8s) was insufficient on slow staging.
    try {
      await Promise.race([
        page.waitForURL(/^(?!.*\/login)/, { timeout: 30000 }),
        page.locator('.error-message').waitFor({ state: 'visible', timeout: 30000 }),
      ]);
    } catch {
      // If both timeout, the test should still check current state
    }
    const leftLogin = !page.url().includes('/login');
    const hasError = (await page.locator('.error-message').count()) > 0;
    expect(leftLogin || hasError).toBe(true) /* acceptable states */;
  });

  test('assets list load completes within reasonable time or shows loading then content', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, .empty-state, .error-display',
    });
    await page.waitForTimeout(2000);
    const hasContent =
      (await page.locator('.asset-list-page').count()) > 0 ||
      (await page.locator('.empty-state').count()) > 0 ||
      (await page.locator('.error-display').count()) > 0;
    expect(hasContent).toBe(true) /* acceptable states */;
  });
});
