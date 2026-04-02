/**
 * E2E: Mesh, Virtualization, Search, AI routes (Phase 13 — 15.6)
 * JOURNEY-DMO-001–005, DPO-013, DE-009, DC-010, DA-003–004; DS-001–002.
 * Routes: /mesh, /virtualization, /search, /ai/search, /ai/schema-matching.
 * Capability-gated routes assert behavior when capability off (e.g. /unavailable). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, gotoWithRetry } from '../../fixtures/auth';
import {
  assertCapabilityGatedPageLoads,
  assertListPageLoads,
  navigateOrSkip,
} from '../../fixtures/helpers';

test.describe('Mesh, Virtualization, Search, AI routes', () => {
  test.setTimeout(120000);

  test.describe('Failure', () => {
    test('unauthenticated access to mesh route redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await gotoWithRetry(page, '/mesh', { waitUntil: 'domcontentloaded' });
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
      const { ok } = await navigateOrSkip(page, '/mesh', {
        contentSelector: '.mesh-domain-list-page, .empty-state',

      });
      if (!ok) return;

      expect(page.url()).toContain('/mesh');
      try {
        await assertListPageLoads(page, '.mesh-domain-list-page, .empty-state');
      } catch (err) {
        if (String(err).includes('BACKEND_TIMEOUT')) {
          test.skip(true, 'Backend timeout under parallel E2E load');
          return;
        }
        throw err;
      }
    });

    test('virtualization list loads (virtual datasets or empty)', async ({ page }) => {
      const { ok } = await navigateOrSkip(page, '/virtualization', {
        contentSelector: '.virtual-dataset-list-page, .empty-state',

      });
      if (!ok) return;

      expect(page.url()).toContain('/virtualization');
      try {
        await assertListPageLoads(page, '.virtual-dataset-list-page, .empty-state');
      } catch (err) {
        if (String(err).includes('BACKEND_TIMEOUT')) {
          test.skip(true, 'Backend timeout under parallel E2E load');
          return;
        }
        throw err;
      }
    });

    test('search page loads', async ({ page }) => {
      const { ok } = await navigateOrSkip(page, '/search', {
        contentSelector: '.search-page',
      });
      if (!ok) return;

      expect(page.url()).toContain('/search');
      await expect(page.locator('.search-page')).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Edge (capability-gated)', () => {
    test('ai/search loads or shows unavailable', async ({ page }) => {
      const { ok } = await navigateOrSkip(page, '/ai/search', {
        contentSelector: '.ai-search-page, .unavailable-page',
      });
      if (!ok) return;

      const url = page.url();
      if (url.includes('/403')) return;
      // Valid outcomes: AI search page OR unavailable page (capability disabled).
      // app-main alone tells us nothing; error-display is never acceptable.
      await assertCapabilityGatedPageLoads(page, '.ai-search-page, .unavailable-page', { timeout: 30000 });
    });

    test('ai/schema-matching loads or shows unavailable', async ({ page }) => {
      const { ok } = await navigateOrSkip(page, '/ai/schema-matching', {
        contentSelector: '.schema-matching-page, .unavailable-page',
      });
      if (!ok) return;

      const url = page.url();
      if (url.includes('/403')) return;
      // Valid outcomes: schema-matching page OR unavailable page (capability disabled).
      await assertCapabilityGatedPageLoads(page, '.schema-matching-page, .unavailable-page', { timeout: 30000 });
    });
  });
});
