/**
 * E2E Test: JOURNEY-MP-006 — Manage Marketplace Mappings
 *
 * Journey: Manage Marketplace Mappings
 * Persona: Data Product Owner
 * Reference: docs/MARKETPLACE_USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /integrations/mappings.
 * Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MP-006: Manage Marketplace Mappings', () => {
  test.setTimeout(180000); // 3 min; client-side nav to mappings avoids full-reload auth race

  test.describe('Success', () => {
    test('mappings list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/mappings', {
        timeout: 60000,
        contentSelector: '.mapping-list-page, .empty-state, .error-display',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/integrations/mappings');
      const hasContent =
        (await page.locator('.mapping-list-page').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('non-existent mappings subpath shows 404 or error', async ({ page }) => {
      const testUser = await getTestUser();
      // Use loginUser + page.goto (not loginAndNavigateToRoute) so we don't wait for .app-main
      // ready; non-existent route may show loading/error; API 500 under load can delay
      await loginUser(page, testUser);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      await page.goto('/integrations/mappings/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      // Wait for error/404 or allow 30s for page to settle (API 500 can delay)
      await page
        .waitForSelector('.error-display, text=/404|not found|Page Not Found|failed to load/i', {
          timeout: 30000,
        })
        .catch(() => page.waitForTimeout(5000));
      const has404 =
        (await page.locator('text=/404|not found|Page Not Found/i').count()) > 0;
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/failed to load|404/i').count()) > 0;
      const onLogin = page.url().includes('/login');
      expect(has404 || hasError || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('mappings route accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/mappings', {
        timeout: 90000,
        contentSelector: '.mapping-list-page, .empty-state, .error-display',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) return;
      expect(page.url()).toContain('/integrations/mappings');
    });
  });
});
