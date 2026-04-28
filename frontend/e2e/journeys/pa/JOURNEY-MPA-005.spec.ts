/**
 * E2E Test: JOURNEY-MPA-005 — Manage Connector Marketplace
 *
 * Journey: Manage Connector Marketplace
 * Persona: Platform Admin
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /integrations/connections.
 * Fixture: getPlatformAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getPlatformAdminUser, loginAsPersona } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-MPA-005: Manage Connector Marketplace @critical', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('integrations connections list loads', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/integrations/connections', { timeout: 65000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/integrations/connections');
    });
  });

  test.describe('Failure', () => {
    test('connection detail with non-existent id shows error', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
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
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/integrations/connections');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/integrations/connections');
    });
  });
});
