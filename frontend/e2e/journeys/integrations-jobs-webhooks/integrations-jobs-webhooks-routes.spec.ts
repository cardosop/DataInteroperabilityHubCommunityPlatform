/**
 * E2E: Integrations, Jobs, Scheduled Ingestion, Webhooks routes (Phase 13 — 15.7)
 * JOURNEY-DE-006, DE-010, TA-008, JOURNEY-MP-001–007.
 * Routes: /integrations/connections, /integrations/sync-jobs, /integrations/mappings,
 *         /jobs, /scheduled-ingestions, /webhooks.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import {
  assertListPageLoads,
  waitForAppMainReady,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('Integrations, Jobs, Scheduled Ingestion, Webhooks routes', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('integrations connections list loads', async ({ page }) => {
      await page.goto('/integrations/connections');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.connection-list-page, .error-display, .empty-state, #email', {
        timeout: 65000,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/integrations/connections');
      // URL check alone is not sufficient — verify actual content; reject error-display
      await assertListPageLoads(page, '.connection-list-page, .empty-state');
    });

    test('integrations sync-jobs list loads', async ({ page }) => {
      await page.goto('/integrations/sync-jobs');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/integrations/sync-jobs');
      // error-display is not an acceptable success outcome for the sync-jobs list
      await assertListPageLoads(page, '.sync-job-list-page, .empty-state');
    });

    test('integrations mappings list loads', async ({ page }) => {
      await page.goto('/integrations/mappings');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/integrations/mappings');
      // error-display is not an acceptable success outcome for the mappings list
      await assertListPageLoads(page, '.mapping-list-page, .empty-state');
    });

    test('jobs list loads', async ({ page }) => {
      await page.goto('/jobs');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.job-list-page, .error-display, .empty-state, #email', {
        timeout: 65000,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/jobs');
      // URL check alone is not sufficient — verify actual content; reject error-display
      await assertListPageLoads(page, '.job-list-page, .empty-state');
    });

    test('webhooks list loads', async ({ page }) => {
      await page.goto('/webhooks');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/webhooks');
      // error-display is not an acceptable success outcome for the webhooks list
      await assertListPageLoads(page, '.webhook-list-page, .empty-state');
    });
  });

  test.describe('Failure', () => {
    test('job detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      // Fixed: use the full UUID path instead of partial includes('/jobs/') && includes('00000000')
      // which could match unrelated requests. Only 404 is valid; no status filter was previously set.
      const responsePromise = page
        .waitForResponse(
          (resp) =>
            resp.url().includes(`/jobs/${nonExistentId}`) &&
            resp.status() === 404,
          { timeout: 15000 }
        )
        .catch(() => null);
      await page.goto(`/jobs/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await responsePromise;

      await page.locator('.error-display, .error-display-title, .job-detail-page')
        .first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);

      const onLogin = page.url().includes('/login');
      if (onLogin) return;

      const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
      const hasNotFoundText = (await page.locator('.error-display-message').filter({ hasText: /not found|could not be found|404|matches the given query/i }).count()) > 0;
      if (hasErrorDisplay && !hasNotFoundText) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`Job detail shows non-404 error for nil UUID: "${errText?.slice(0, 200)}". Expected "not found".`);
      }
      expect(hasErrorDisplay && hasNotFoundText).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('scheduled-ingestions loads or redirects by role', async ({ page }) => {
      await page.goto('/scheduled-ingestions');
      await page.waitForLoadState('domcontentloaded');
      // Wait for a terminal state — list, error, 403, unavailable, or redirect to login.
      // Loading spinner alone is NOT a terminal state; increase timeout to reach one.
      await page
        .locator(
          '.scheduled-ingestion-list-page, .empty-state, .error-display, .unavailable-page, #email'
        )
        .first()
        .waitFor({ state: 'visible', timeout: 40000 })
        .catch(() => null);
      const url = page.url();
      const onScheduled = url.includes('/scheduled-ingestions');
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const hasList = (await page.locator('.scheduled-ingestion-list-page').count()) > 0;
      const hasError = (await page.locator('.error-display').count()) > 0;
      const has403 = (await page.locator('text=/403|forbidden/i').count()) > 0;
      const hasUnavailable = (await page.locator('.unavailable-page').count()) > 0;
      const hasEmptyState = (await page.locator('.empty-state').count()) > 0;
      expect(onScheduled || onLogin || on403).toBe(true);
      // Terminal states only: list, empty state, error, 403 text, unavailable, or redirect
      expect(hasList || hasEmptyState || hasError || has403 || hasUnavailable || onLogin || on403).toBe(true);
    });
  });
});
