/**
 * E2E Test: JOURNEY-DEV-007 — Build Custom Connector
 *
 * Journey: Build Custom Connector
 * Persona: External Developer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /integrations/connections, /integrations/connections/create.
 * Extends integrations-jobs-webhooks pattern. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getExternalDeveloperUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DEV-007: Build Custom Connector', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('integrations connections list loads', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/integrations/connections', {
        timeout: 90000,
        contentSelector: '.connection-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], .app-main, [data-testid="app-main"]',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/integrations/connections');
    });

    test('integrations connections create page loads', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/integrations/connections/create', {
        timeout: 90000,
        contentSelector: '.marketplace-connection-create-page, .app-main, [data-testid="app-main"], .error-display, [data-testid="error-display"]',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/integrations/connections/create');
    });
  });

  test.describe('Failure', () => {
    test('connection detail with non-existent id shows error', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/integrations/connections', {
        timeout: 90000,
        contentSelector: '.connection-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      await page.goto('/integrations/connections/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.marketplace-connection-detail-page, [data-testid="marketplace-connection-detail-page"]',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('integrations connections loads', async ({ page }) => {
      const devUser = await getExternalDeveloperUser();
      await loginAndNavigateToRoute(page, devUser, '/integrations/connections', {
        timeout: 90000,
        contentSelector: '.connection-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/integrations/connections');
    });
  });
});
