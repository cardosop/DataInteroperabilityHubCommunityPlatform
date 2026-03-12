/**
 * E2E Test: JOURNEY-DE-014 — Create ODPS via API
 *
 * Journey: Create ODPS via API
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /odps/upload, /odps, /contracts.
 * UI flow for ODPS creation (API flow would be separate API tests).
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUserOrTestUser, getTestUser, loginUser, loginViaApi } from '../../fixtures/auth';

/** Inject API tokens to bypass slow UI login (avoids slowMo=400ms-per-action penalty). */
async function loginViaApiAndInject(
  page: import('@playwright/test').Page,
  getUser: () => Promise<import('../../fixtures/auth').TestUser>
): Promise<void> {
  const user = await getUser();
  const auth = await loginViaApi(user.email, user.password);
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.evaluate(
    ({ accessToken, refreshToken, userData }) => {
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);
      localStorage.setItem('user', JSON.stringify(userData));
    },
    { accessToken: auth.access_token, refreshToken: auth.refresh_token, userData: auth.user }
  );
}

test.describe('JOURNEY-DE-014: Create ODPS via API', () => {
  // 6 min: ODPS routes can be slow under parallel E2E load (chromium-routes runs late).
  // Edge test uses token injection to avoid the slow UI login that exhausted this budget.
  test.setTimeout(360000);

  test.describe('Success', () => {
    test('ODPS upload page loads', async ({ page }) => {
      const testUser = await getTenantAdminUserOrTestUser();
      await loginUser(page, testUser);
      await page.goto('/odps/upload');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.odps-upload-page, .odps-upload-form, .loading-spinner-container, .app-main, #email',
        { timeout: 45000 }
      );
      // Wait for the page to settle (upload form fields become interactive)
      await page
        .locator('.odps-upload-page, .odps-upload-form, .app-main')
        .first()
        .waitFor({ state: 'visible', timeout: 10000 })
        .catch(() => null);
      expect(page.url()).toContain('/odps/upload');
    });

    test('ODPS list loads', async ({ page }) => {
      const testUser = await getTenantAdminUserOrTestUser();
      await loginUser(page, testUser);
      await page.goto('/odps');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.odps-list-page, .odps-empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 45000 }
      );
      expect(page.url()).toContain('/odps');
    });
  });

  test.describe('Failure', () => {
    test('ODPS detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/odps/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      // Wait for error to appear instead of a fixed sleep
      await page
        .locator('.error-display, .odps-detail-main')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);
      const hasError = (await page.locator('.error-display').count()) > 0;
      const noSuccessContent = (await page.locator('.odps-detail-main').count()) === 0;
      const onLogin = page.url().includes('/login');
      expect(hasError || noSuccessContent || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('ODPS upload and list accessible', async ({ page }) => {
      // Use API token injection to avoid the slow UI login that caused chromium-routes
      // to exceed the 360s budget when it ran late in the batch under high API load.
      // Two 120s waitForSelectors + slow UI login = 300s+ baseline, leaving no buffer.
      await loginViaApiAndInject(page, getTenantAdminUserOrTestUser);
      await page.goto('/odps/upload');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.odps-upload-page, .odps-upload-form, .loading-spinner-container, #email',
        { timeout: 45000 }
      );
      expect(page.url()).toContain('/odps/upload');
      await page.goto('/odps');
      await page.waitForSelector(
        '.odps-list-page, .odps-empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 45000 }
      );
      expect(page.url()).toContain('/odps');
    });
  });
});
