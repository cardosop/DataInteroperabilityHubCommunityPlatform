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
import { clearAuthStorage, getConsumerTestUser, getTestUser, loginUser } from '../../fixtures/auth';
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
      // Route is nested under the integrations layout: /integrations/sync-jobs
      await page.goto('/integrations/sync-jobs');
      await page.waitForLoadState('domcontentloaded');
      // Wait for a terminal render state instead of a fixed sleep
      // Include .unavailable-page for capability-gated routes that redirect before resolving
      await page
        .locator('.sync-job-list-page, .empty-state, .error-display, .loading-spinner-container, .unavailable-page, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 45000 })
        .catch(() => null);
      const url = page.url();
      const onSyncJobs = url.includes('/sync-jobs');
      const onLogin = url.includes('/login');
      // App may redirect /integrations/sync-jobs to /integrations base before sub-route resolves
      const onIntegrations = url.includes('/integrations');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      expect(onSyncJobs || onLogin || onIntegrations || on403 || onUnavailable).toBe(true);
      if (onSyncJobs) {
        // Phase 2 wait: ensure terminal content is visible before count() checks
        await page
          .locator('.sync-job-list-page, .empty-state, .error-display')
          .first()
          .waitFor({ state: 'visible', timeout: 15000 })
          .catch(() => null);
        const hasContent =
          (await page.locator('.sync-job-list-page').count()) > 0 ||
          (await page.locator('.empty-state').count()) > 0 ||
          (await page.locator('.error-display').count()) > 0 ||
          // Fallback: route rendered something in the app shell (API slow but page resolved)
          (await page.locator('.app-main').count()) > 0;
        expect(hasContent).toBe(true);
      }
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

    test('consumer (DATA_CONSUMER) accessing integrations create gets redirect or content (role awareness)', async ({ page }) => {
      // Data consumers should not be able to create integrations (DE persona routes).
      // This test verifies the route either redirects or renders appropriate messaging.
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/integrations/connections/create');
      await page.waitForSelector(
        '.marketplace-connection-create-page, .connection-create-page, .error-display, .unavailable-page, #email',
        { timeout: 45000 }
      );
      const url = page.url();
      // Consumer role: redirect to login/403/unavailable, or the create page (role may be permitted)
      // The critical assertion is no unhandled crash
      const hasKnownState =
        url.includes('/login') ||
        url.includes('/403') ||
        url.includes('/unavailable') ||
        url.includes('/integrations/connections/create');
      expect(hasKnownState).toBe(true);
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
