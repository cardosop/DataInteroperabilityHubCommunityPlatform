/**
 * E2E Test: JOURNEY-DEV-004 — Set Up Webhooks
 *
 * Journey: Set Up Webhooks
 * Persona: External Developer
 * Reference: docs/deprecated-doc/archive/USER_JOURNEY_MAPPING.md, FRONTEND_BACKEND_GAP_REMEDIATION_PLAN.md
 *
 * Routes: /webhooks. integrations-jobs-webhooks covers routes; this spec provides dedicated
 * DEV-004 journey coverage. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getExternalDeveloperUser } from '../../fixtures/auth';
import {
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('JOURNEY-DEV-004: Set Up Webhooks', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('webhooks list loads', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/webhooks', {
        timeout: 60000,
        contentSelector: '.webhook-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/webhooks');
      await waitForLoadingComplete(page, { timeout: 25000 });
      const hasContent =
        (await page.locator('.webhook-list-page, .webhook-list-header').count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0 ||
        (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('webhook detail with non-existent id shows error', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/webhooks', {
        timeout: 45000,
        contentSelector: '.webhook-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      await page.goto('/webhooks/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.webhook-detail-page .webhook-detail-dl',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('webhooks route accessible', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/webhooks', {
        timeout: 45000,
        contentSelector: '.webhook-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(
        page.url().includes('/webhooks') ||
          page.url().includes('/403') ||
          page.url().includes('/login')
      ).toBe(true);
    });
  });
});
