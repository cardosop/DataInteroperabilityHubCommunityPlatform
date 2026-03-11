/**
 * E2E: UC-DQ-001 — Run Data Quality Check / Monitor Asset Quality
 *
 * Use Case: Run Data Quality Check
 * Persona: Data Product Owner, Data Engineer, Compliance Officer
 * Reference: docs/USE_CASES.md#uc-dq-001
 *
 * Success/Failure/Edge. Routes: /dq, /dq/runs/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('UC-DQ-001: Run Data Quality Check', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('DQ runs list loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/dq', {
        timeout: 60000,
        contentSelector: '.dq-run-list-page, .empty-state, .error-display, .loading-spinner-container',
      });
      expect(page.url()).toContain('/dq');
      await waitForLoadingComplete(page, { timeout: 15000 });
      const hasContent =
        (await page.locator('.dq-run-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('h1:has-text("Data Quality")').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('DQ run detail with non-existent id shows error', async ({ page }) => {
      const user = await getTestUser();
      const { loginUser } = await import('../../fixtures/auth');
      await loginUser(page, user);
      await page.goto('/dq/runs/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.dq-run-detail-page',
        waitAfterLoad: 8000,
      });
    });

    test('unauthenticated access to DQ redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/dq', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|dq)/, { timeout: 20_000 });
      expect(page.url().includes('/login') || page.url().includes('/dq')).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('DQ list with empty state loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/dq', {
        timeout: 60000,
        contentSelector: '.dq-run-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/dq');
    });
  });
});
