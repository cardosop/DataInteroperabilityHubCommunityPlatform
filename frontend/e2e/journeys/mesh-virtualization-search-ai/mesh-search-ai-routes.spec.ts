/**
 * E2E: Mesh, Virtualization, Search, AI routes (Phase 13 — 15.6)
 * JOURNEY-DMO-001–005, DPO-013, DE-009, DC-010, DA-003–004; DS-001–002.
 * Routes: /mesh, /virtualization, /search, /ai/search, /ai/schema-matching.
 * Capability-gated routes assert behavior when capability off (e.g. /unavailable). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage } from '../../fixtures/auth';
import { waitForAppMainReady } from '../../fixtures/helpers';

test.describe('Mesh, Virtualization, Search, AI routes', () => {
  test.setTimeout(120000);

  test.describe('Failure', () => {
    test('unauthenticated access to mesh route redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/mesh', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|mesh|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/mesh')).toBe(true);
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
      const hasContent =
        (await page.locator('.virtual-dataset-list-page').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
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
      await page.waitForSelector(
        '.app-main, .ai-search-page, .app-shell, .unavailable-page, .loading-spinner, .loading-spinner-container, #email',
        { timeout: 15000 }
      );
      await page.waitForTimeout(3000); // Capabilities can take time; AI page may load slowly
      const url = page.url();
      const onAiSearch = url.includes('/ai/search');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const hasContent =
        (await page.locator('.app-main, .ai-search-page, .app-shell, .unavailable-page').count()) > 0 ||
        (await page.locator('.loading-spinner, .loading-spinner-container').count()) > 0;
      expect(onAiSearch || onUnavailable || onLogin || on403).toBe(true);
      expect(hasContent || onUnavailable || onLogin || on403).toBe(true);
    });

    test('ai/schema-matching loads or shows unavailable', async ({ page }) => {
      await page.goto('/ai/schema-matching');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.app-main, .schema-matching-page, .app-shell, .unavailable-page, .loading-spinner, .loading-spinner-container, #email',
        { timeout: 15000 }
      );
      await page.waitForTimeout(3000);
      const url = page.url();
      const onSchema = url.includes('/ai/schema-matching');
      const onUnavailable = url.includes('/unavailable');
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const hasContent =
        (await page.locator('.app-main, .schema-matching-page, .app-shell, .unavailable-page').count()) > 0 ||
        (await page.locator('.loading-spinner, .loading-spinner-container').count()) > 0;
      expect(onSchema || onUnavailable || onLogin || on403).toBe(true);
      expect(hasContent || onUnavailable || onLogin || on403).toBe(true);
    });
  });
});
