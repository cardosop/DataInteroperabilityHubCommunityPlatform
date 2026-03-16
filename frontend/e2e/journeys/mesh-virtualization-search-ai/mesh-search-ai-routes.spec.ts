/**
 * E2E: Mesh, Virtualization, Search, AI routes (Phase 13 — 15.6)
 * JOURNEY-DMO-001–005, DPO-013, DE-009, DC-010, DA-003–004; DS-001–002.
 * Routes: /mesh, /virtualization, /search, /ai/search, /ai/schema-matching.
 * Capability-gated routes assert behavior when capability off (e.g. /unavailable). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage } from '../../fixtures/auth';
import {
  assertCapabilityGatedPageLoads,
  assertListPageLoads,
  waitForAppMainReady,
} from '../../fixtures/helpers';

test.describe('Mesh, Virtualization, Search, AI routes', () => {
  test.setTimeout(120000);

  test.describe('Failure', () => {
    test('unauthenticated access to mesh route redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/mesh', { waitUntil: 'domcontentloaded' });
      // Only /login or /403 are valid redirect destinations for unauthenticated access.
      // If the URL still contains /mesh it means the auth guard is missing — that is the
      // security bug this test exists to catch, and it must FAIL the test.
      await page.waitForURL(/\/(login|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403')).toBe(true);
    });
  });

  test.describe('Success', () => {
    test('mesh list loads (domains or empty)', async ({ page }) => {
      await page.goto('/mesh');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.mesh-domain-list-page, .error-display, .empty-state, #email', {
        timeout: 65000,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/mesh');
      // URL check alone is not sufficient — verify actual content is visible and no error shown
      await assertListPageLoads(page, '.mesh-domain-list-page, .empty-state');
    });

    test('virtualization list loads (virtual datasets or empty)', async ({ page }) => {
      await page.goto('/virtualization');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.virtual-dataset-list-page, .error-display, .empty-state, #email',
        { timeout: 65000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/virtualization');
      // error-display is not an acceptable success outcome for the virtualization list
      await assertListPageLoads(page, '.virtual-dataset-list-page, .empty-state');
    });

    test('search page loads', async ({ page }) => {
      await page.goto('/search');
      try {
        await waitForAppMainReady(page, { contentSelector: '.search-page', timeout: 60000 });
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
      expect(page.url()).toContain('/search');
      await expect(page.locator('.search-page')).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Edge (capability-gated)', () => {
    test('ai/search loads or shows unavailable', async ({ page }) => {
      await page.goto('/ai/search');
      await page.waitForLoadState('domcontentloaded');
      // CapabilityRoute shows LoadingSpinner while capabilities load; do NOT include spinner in
      // the wait selector (it resolves immediately but the page isn't terminal yet). Wait for
      // the actual page or unavailable state — use 45s to cover slow-backend capability fetches.
      await page
        .locator('.ai-search-page, .unavailable-page, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 45000 })
        .catch(() => null);
      const url = page.url();
      if (url.includes('/login') || url.includes('/403')) return;
      // Valid outcomes: AI search page OR unavailable page (capability disabled).
      // app-main alone tells us nothing; error-display is never acceptable.
      await assertCapabilityGatedPageLoads(page, '.ai-search-page, .unavailable-page', { timeout: 30000 });
    });

    test('ai/schema-matching loads or shows unavailable', async ({ page }) => {
      await page.goto('/ai/schema-matching');
      await page.waitForLoadState('domcontentloaded');
      // CapabilityRoute shows LoadingSpinner while capabilities load; do NOT include spinner in
      // the wait selector (it resolves immediately but the page isn't terminal yet). Wait for the
      // actual page or unavailable state — use 45s to cover slow-backend capability fetches.
      await page
        .locator('.schema-matching-page, .unavailable-page, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 45000 })
        .catch(() => null);
      const url = page.url();
      if (url.includes('/login') || url.includes('/403')) return;
      // Valid outcomes: schema-matching page OR unavailable page (capability disabled).
      await assertCapabilityGatedPageLoads(page, '.schema-matching-page, .unavailable-page', { timeout: 30000 });
    });
  });
});
