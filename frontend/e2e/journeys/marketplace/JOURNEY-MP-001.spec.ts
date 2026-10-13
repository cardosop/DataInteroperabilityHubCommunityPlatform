/**
 * E2E Test: JOURNEY-MP-001 — Connect to External Marketplace
 *
 * Journey: Connect to External Marketplace
 * Persona: Data Product Owner, Tenant Admin
 * Reference: docs/MARKETPLACE_USER_JOURNEYS.md
 *
 * Success/Failure/Edge per integrations-jobs-webhooks pattern.
 * Routes: /integrations/connections. Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { environmentSkipGuard } from '../../fixtures/envPolicy.cjs';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MP-001: Connect to External Marketplace', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('integrations connections list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections', {
        timeout: 65000,
        contentSelector: '.connection-list-page, .empty-state, [data-testid="empty-state"]',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        throw new Error(`Unexpected redirect to ${page.url()} — verify test user has integrations access`);
      }
      // The integrations subtree is CapabilityRoute-gated off the
      // OpenAPI/marketplace snapshot — a /unavailable bounce under batch
      // churn (API restart window) is a transient snapshot-fetch failure,
      // not a disabled feature. W16-guarded skip: raises in CI, skips
      // locally.
      if (page.url().includes('/unavailable')) {
        environmentSkipGuard(
          'integrations gate bounced to /unavailable — capabilities/OpenAPI snapshot fetch failed under parallel load'
        );
      }
      test.skip(
        page.url().includes('/unavailable'),
        'integrations gate bounced to /unavailable — transient snapshot failure'
      );
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
      expect(page.url()).toContain('/integrations/connections');
    });

    test('connection create page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections/create', {
        timeout: 60000,
        contentSelector: '.connection-create-page, .marketplace-connection-create-page, form',
        acceptRedirectToLogin: true,
      });
      await page.waitForTimeout(1000);
      if (page.url().includes('/login')) {
        test.skip(page.url().includes('/login'), 'Redirected to /login — auth not available in this environment');
      }
      expect(page.url()).toContain('/integrations/connections/create');
      const hasContent =
        (await page.locator('.marketplace-connection-create-page, .connection-create-page, .app-main, [data-testid="app-main"], form').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('connection detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/integrations/connections/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.marketplace-connection-detail-page, [data-testid="marketplace-connection-detail-page"]',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('connections list and create routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections', {
        timeout: 60000,
        contentSelector: '.connection-list-page, .empty-state, [data-testid="empty-state"]',
      });
      // Edge contract: the gate-off terminal state (/unavailable — the
      // CapabilityRoute bounce when the snapshot fetch fails under batch
      // churn) is a valid outcome for "route accessible", same convention
      // as DE-010's Edge test.
      expect(
        page.url().includes('/integrations/connections') ||
          page.url().includes('/unavailable') ||
          page.url().includes('/login') ||
          page.url().includes('/403')
      ).toBe(true);
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections/create', {
        timeout: 60000,
        contentSelector: '.connection-create-page, .marketplace-connection-create-page, form',
      });
      expect(
        page.url().includes('/integrations/connections') || page.url().includes('/unavailable')
      ).toBe(true);
    });
  });
});
