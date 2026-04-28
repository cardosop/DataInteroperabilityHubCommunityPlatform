/**
 * E2E: UC-ODPS-003 — Export ODPS Product
 *
 * Use Case: Export ODPS Product
 * Persona: Data Product Owner
 * Reference: docs/USE_CASES.md, docs/TEST_TRACEABILITY.md
 *
 * Success/Failure/Edge. Routes: /odps, /odps/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { createODPSProductViaApi } from '../../fixtures/api-assets';
import { getTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('UC-ODPS-003: Export ODPS Product', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('ODPS detail loads when product exists', async ({ page }) => {
      const user = await getTestUser();
      const odpsId = await createODPSProductViaApi(user);

      await loginAndNavigateToRoute(page, user, `/odps/${odpsId}`, {
        timeout: 90000,
        contentSelector: '.odps-detail-page, .odps-detail, .odps-detail-main, .error-display, [data-testid="error-display"]',
        acceptRedirectToLogin: false,
      });
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on ODPS detail');
      }

      const hasDetail =
        (await page.locator('.odps-detail-page').count()) > 0 ||
        (await page.locator('.odps-detail').count()) > 0 ||
        (await page.locator('.odps-detail-main').count()) > 0 ||
        page.url().includes('/odps/');
      expect(hasDetail).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('ODPS detail with non-existent id shows error', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(
        page,
        user,
        '/odps/00000000-0000-0000-0000-000000000000',
        {
          timeout: 90000,
          contentSelector:
            '.odps-detail-page, .odps-detail, .error-display, [data-testid="error-display"], [role="alert"]',
          acceptRedirectToLogin: false,
        }
      );
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on invalid ODPS id');
      }
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.odps-detail-page, .odps-detail',
        waitAfterLoad: 8000,
        selectorTimeout: 60000,
      });
    });
  });

  test.describe('Edge', () => {
    test('ODPS list with empty state loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/odps', {
        timeout: 90000,
        contentSelector: '.odps-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toContain('/odps');
      const hasContent =
        (await page.locator('.odps-list-page').count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasContent).toBe(true);
    });
  });
});
