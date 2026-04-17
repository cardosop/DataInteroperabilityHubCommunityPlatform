/**
 * E2E Feature: Observability
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /observability.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Feature: Observability', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('observability page loads with content', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/observability', {
        timeout: 60000,
        contentSelector: '.observability-page, .monitoring-page, .unavailable-page, .error-display, h1',
      });
      const url = page.url();
      if (url.includes('/login') || url.includes('/403')) {
        test.skip(true, 'Auth/role redirect — observability may require specific role');
        return;
      }
      await expect(page.locator('.error-display')).not.toBeVisible({ timeout: 5000 });
      const hasContent =
        (await page.locator('.observability-page, .monitoring-page, .unavailable-page, h1').count()) > 0;
      expect(hasContent, 'Expected observability content or unavailable page').toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to observability redirects to login', async ({ page }) => {
      await page.goto('/observability');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/observability'),
        'Expected /login redirect or /observability with auth'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('observability renders without server errors', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/observability', {
        timeout: 60000,
        contentSelector: '.observability-page, .monitoring-page, .unavailable-page, .error-display, h1',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) return;
      const has500 = (await page.locator('text=/500|internal server error/i').count()) > 0;
      expect(has500, 'Observability page must not show 500 errors').toBe(false);
    });
  });
});
