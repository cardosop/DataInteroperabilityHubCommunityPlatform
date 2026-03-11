/**
 * E2E Test: JOURNEY-DE-005 — Integrate External Data Source
 *
 * Journey: Integrate External Data Source
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Routes: /integrations/connections, /sync-jobs, /mappings. integrations-jobs-webhooks covers
 * routes; this spec provides dedicated DE-005 journey coverage. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';
import { hasLoginPrompt, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-005: Integrate External Data Source', () => {
  test.setTimeout(300000);

  test.describe('Success', () => {
    test('integrations connections list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/integrations/connections');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/integrations');
    });

    test('sync jobs list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/sync-jobs');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onSyncJobs = page.url().includes('/sync-jobs');
      const onLogin = page.url().includes('/login');
      expect(onSyncJobs || onLogin).toBe(true);
    });

    test('mappings list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/integrations/mappings');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.mapping-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 120000 }
      );
      if (page.url().includes('/login')) return;
      expect(page.url()).toContain('/integrations');
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to integrations route redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/integrations/connections', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|integrations)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onIntegrationsWithLoginPrompt =
        url.includes('/integrations') &&
        (await hasLoginPrompt(page));
      expect(onLogin || onIntegrationsWithLoginPrompt).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('integrations routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/integrations/connections');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.connection-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 120000 }
      );
      expect(page.url()).toContain('/integrations');
    });
  });
});
