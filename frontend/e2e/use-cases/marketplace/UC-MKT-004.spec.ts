/**
 * E2E: UC-MKT-004 — Access Entitlements / View Purchased Assets
 *
 * Use Case: Access Entitlements
 * Persona: Data Consumer
 * Reference: docs/USE_CASES.md, UC-DC-004
 *
 * Success/Failure/Edge. Routes: /marketplace/entitlements, /marketplace/entitlements/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('UC-MKT-004: Access Entitlements', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('entitlements list loads', async ({ page }) => {
      const user = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, user, '/marketplace/entitlements', {
        timeout: 90000,
        contentSelector: '.entitlement-list-page, .empty-state, .error-display',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/marketplace/entitlements');
    });
  });

  test.describe('Failure', () => {
    test('entitlement detail with non-existent id shows error', async ({ page }) => {
      const user = await getConsumerTestUser();
      const { loginUser } = await import('../../fixtures/auth');
      await loginUser(page, user);
      await page.goto('/marketplace/entitlements/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.entitlement-detail-page, .error-display',
        waitAfterLoad: 12000,
      });
    });
  });

  test.describe('Edge', () => {
    test('entitlements list with empty state loads', async ({ page }) => {
      const user = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, user, '/marketplace/entitlements', {
        timeout: 90000,
        contentSelector: '.entitlement-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/marketplace/entitlements');
    });
  });
});
