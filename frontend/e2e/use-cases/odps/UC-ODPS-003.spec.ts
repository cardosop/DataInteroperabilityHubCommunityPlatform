/**
 * E2E: UC-ODPS-003 — Export ODPS Product
 *
 * Use Case: Export ODPS Product
 * Persona: Data Product Owner
 * Reference: docs/USE_CASES.md, docs/TEST_TRACEABILITY.md
 *
 * Success/Failure/Edge. Routes: /odps, /odps/:id (legacy — Phase 211.A6
 * redirects them to /contracts?spec_type=ODPS and /contracts/:id).
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

      // /odps/:id redirects (Phase 211.A6) to the contract detail page — the
      // ODPS product is a contract internally, so the contract page renders it.
      await loginAndNavigateToRoute(page, user, `/odps/${odpsId}`, {
        timeout: 90000,
        contentSelector: '.contract-detail-page, [data-testid="contract-detail-page"], .error-display, [data-testid="error-display"]',
        acceptRedirectToLogin: false,
      });
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on ODPS detail');
      }

      expect(page.url()).toContain(`/contracts/${odpsId}`);
      const hasDetail =
        (await page.locator('.contract-detail-page, [data-testid="contract-detail-page"]').count()) > 0;
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
            '.contract-detail-page, [data-testid="contract-detail-page"], .error-display, [data-testid="error-display"], [role="alert"]',
          acceptRedirectToLogin: false,
        }
      );
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on invalid ODPS id');
      }
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.contract-detail-page, [data-testid="contract-detail-page"]',
        waitAfterLoad: 8000,
        selectorTimeout: 60000,
      });
    });
  });

  test.describe('Edge', () => {
    test('ODPS list with empty state loads', async ({ page }) => {
      const user = await getTestUser();
      // Legacy /odps redirects (Phase 211.A6) to the contracts list filtered by spec_type=ODPS.
      await loginAndNavigateToRoute(page, user, '/odps', {
        timeout: 90000,
        contentSelector: '.contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toContain('/contracts?spec_type=ODPS');
      const hasContent =
        (await page.locator('.contract-list-page, [data-testid="contract-list-page"]').count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasContent).toBe(true);
    });
  });
});
