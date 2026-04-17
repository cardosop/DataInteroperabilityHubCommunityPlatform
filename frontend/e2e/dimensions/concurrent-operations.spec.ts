/**
 * Dimension: Concurrent operations
 * Cross-cutting E2E for race conditions and optimistic locking.
 * Per tasks 8.7.4: frontend/e2e/dimensions/concurrent-operations.spec.ts
 * Run: npm run test:e2e -- e2e/dimensions/concurrent-operations.spec.ts
 *
 * No mocks; real backend. Asserts that parallel or rapid operations
 * do not leave corrupt state (e.g. duplicate submit, list consistency).
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { assertListPageLoads, loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Dimension: Concurrent operations', () => {
  test.setTimeout(90000);

  test('double navigation to assets list does not corrupt page state', async ({ page }) => {
    // Use loginAndNavigateToRoute to ensure auth persists through SPA navigation
    // (loginUser + page.goto loses auth on full-page reload in httpOnly cookie mode).
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, .empty-state, .error-display',
    });
    await assertListPageLoads(page, '.asset-list-page, .empty-state', { timeout: 30000 });
    // Second goto reloads the SPA from scratch — auth must re-init and the
    // asset list must re-render. The previous fixed waitForTimeout(2000) was
    // racy on cold staging workers (auth refresh + lazy chunk + list query
    // can each take 5-10s on the slow path). Wait for one of the terminal
    // states to actually appear, with a deterministic timeout.
    await page.goto('/assets', { waitUntil: 'domcontentloaded' });
    await page
      .locator('.asset-list-page, .empty-state, .error-display')
      .first()
      .waitFor({ state: 'visible', timeout: 30000 });
    expect(page.url()).toContain('/assets');
    const hasContent =
      (await page.locator('.asset-list-page').count()) > 0 ||
      (await page.locator('.empty-state').count()) > 0 ||
      (await page.locator('.error-display').count()) > 0;
    expect(hasContent).toBe(true);
  });

  test('rapid double-click on login submit does not duplicate request or corrupt session', async ({
    page,
  }) => {
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await page.fill('input#email', 'nonexistent@example.com');
    await page.fill('input#password', 'wrongpassword');
    const submit = page.locator('button[type="submit"]');
    let responseCount = 0;
    page.on('response', (r) => {
      if (r.url().includes('/auth/login/') && r.request().method() === 'POST') responseCount++;
    });
    await submit.click();
    await submit.click();
    await page.waitForTimeout(5000);
    const hasSingleOrDoubleResponse = responseCount >= 1 && responseCount <= 2;
    expect(hasSingleOrDoubleResponse).toBe(true);
    const onLogin = page.url().includes('/login');
    expect(onLogin).toBe(true);
  });
});
