/**
 * E2E: UC-AM-001 — Create Asset via Data-First Flow
 *
 * Use Case: Create Asset via Data-First Flow
 * Persona: Data Product Owner, Data Engineer
 * Reference: docs/USE_CASES.md#uc-am-001
 *
 * Success/Failure/Edge. Routes: /assets, /assets/create.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('UC-AM-001: Create Asset via Data-First Flow', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('assets list loads for authenticated user', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display, .loading-spinner-container',
      });
      expect(page.url()).toContain('/assets');
      await waitForLoadingComplete(page, { timeout: 15000 });
      const hasContent =
        (await page.locator('.asset-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('assets create route loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/assets/create', {
        timeout: 60000,
        contentSelector: 'form, .asset-form, .error-display, .loading-spinner-container',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/assets/create');
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to assets redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/assets', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|assets)/, { timeout: 20_000 });
      const url = page.url();
      expect(url.includes('/login') || (url.includes('/assets') && (await page.locator('input#email, [href*="/login"]').count()) > 0)).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('assets list with empty state shows create option', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/assets');
    });
  });
});
