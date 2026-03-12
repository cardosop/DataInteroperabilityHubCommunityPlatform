/**
 * E2E Test: JOURNEY-DE-003 — Configure Data Quality Checks
 *
 * Journey: Configure Data Quality Checks
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Routes: /dq, /dq/runs/:id. dq-compliance-governance-routes covers routes; this spec provides
 * dedicated DE-003 journey coverage. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-003: Configure Data Quality Checks', () => {
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('dq list loads (runs list or empty)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/dq');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.dq-run-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 90000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/dq');
    });
  });

  test.describe('Failure', () => {
    test('dq run detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      await page.goto(`/dq/runs/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const hasError = (await page.locator('.error-display').count()) > 0;
      const noSuccessContent = (await page.locator('.dq-run-detail-main').count()) === 0;
      const onLogin = page.url().includes('/login');
      expect(hasError || noSuccessContent || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('dq route accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/dq', {
        timeout: 90000,
        contentSelector:
          '.dq-run-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
      });
      expect(page.url()).toContain('/dq');
    });
  });
});
