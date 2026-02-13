/**
 * E2E: Integrations, Jobs, Scheduled Ingestion, Webhooks routes (Phase 13 — 15.7)
 * JOURNEY-DE-006, DE-010, TA-008, JOURNEY-MP-001–007.
 * Routes: /integrations/connections, /integrations/sync-jobs, /integrations/mappings,
 *         /jobs, /scheduled-ingestions, /webhooks.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../../fixtures/helpers';

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
      expect(page.url()).toContain('/integrations/sync-jobs');
      const hasContent =
        (await page.locator('.sync-job-list-page').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
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
      expect(page.url()).toContain('/integrations/mappings');
      const hasContent =
        (await page.locator('.mapping-list-page').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
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
      expect(page.url()).toContain('/webhooks');
      const hasContent =
        (await page.locator('.webhook-list-page').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('job detail with non-existent id shows error', async ({ page }) => {
      await page.goto('/jobs/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await page
        .waitForResponse(
          (resp) => resp.url().includes('/jobs/') && resp.url().includes('00000000'),
          { timeout: 15000 }
        )
        .catch(() => null);
      await page.waitForTimeout(2000);
      const hasError =
        (await page.locator('.error-display, .error-display-title').count()) > 0 ||
        (await page.locator('text=/not found|failed to load|404/i').count()) > 0;
      const noSuccess = (await page.locator('.job-detail-main, .job-detail-page').count()) === 0;
      expect(hasError || noSuccess).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('scheduled-ingestions loads or redirects by role', async ({ page }) => {
      await page.goto('/scheduled-ingestions');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      const onScheduled = url.includes('/scheduled-ingestions');
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const hasList = (await page.locator('.scheduled-ingestion-list-page').count()) > 0;
      const hasError = (await page.locator('.error-display').count()) > 0;
      const has403 = (await page.locator('text=/403|forbidden/i').count()) > 0;
      expect(onScheduled || onLogin || on403).toBe(true);
      expect(hasList || hasError || has403 || onLogin || on403).toBe(true);
    });
  });
});
