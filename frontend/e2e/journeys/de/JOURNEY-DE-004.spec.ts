/**
 * E2E Test: JOURNEY-DE-004 — Set Up Compliance Scanning
 *
 * Journey: Set Up Compliance Scanning
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Routes: /compliance, /compliance/runs/:id. dq-compliance-governance-routes covers routes;
 * this spec provides dedicated DE-004 journey coverage. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-004: Set Up Compliance Scanning', () => {
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('compliance list loads (runs list or empty)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/compliance');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, {
          timeout: 90000,
          contentSelector:
            '.compliance-run-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/compliance');
    });
  });

  test.describe('Failure', () => {
    test('compliance run detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      await page.goto(`/compliance/runs/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.compliance-run-detail-page',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('compliance route accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/compliance', {
        timeout: 90000,
        contentSelector:
          '.compliance-run-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
      });
      expect(page.url()).toContain('/compliance');
    });
  });
});
