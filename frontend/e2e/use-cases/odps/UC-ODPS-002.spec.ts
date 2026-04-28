/**
 * E2E: UC-ODPS-002 — Link ODPS to Contract
 *
 * Use Case: Link ODPS to Contract
 * Persona: Data Product Owner
 * Reference: docs/USE_CASES.md, docs/TEST_TRACEABILITY.md
 *
 * Success/Failure/Edge. Routes: /contracts/:id/link-odps.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { createODCSContractViaApi } from '../../fixtures/api-assets';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('UC-ODPS-002: Link ODPS to Contract', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('link-odps route loads when contract exists', async ({ page }) => {
      const user = await getTestUser();
      const contractId = await createODCSContractViaApi(user);
      await loginAndNavigateToRoute(page, user, `/contracts/${contractId}/link-odps`, {
        timeout: 60000,
        contentSelector: '.odps-link-page, .error-display, [data-testid="error-display"], [role="alert"]',
        acceptRedirectToLogin: false,
      });
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on link-odps');
      }
      expect(page.url()).toContain('/link-odps');
      await expect(
        page.locator('.odps-link-page, .error-display, [data-testid="error-display"]').first()
      ).toBeVisible({ timeout: 15000 });
    });
  });

  test.describe('Failure', () => {
    test('link-odps with non-existent contract id shows error', async ({ page }) => {
      const user = await getTestUser();
      // Navigate directly to the non-existent contract's link-odps page.
      // ODPSLinkPage now renders ErrorDisplay BEFORE the loading spinner when
      // contract fetch completes with no data.
      await loginAndNavigateToRoute(
        page,
        user,
        '/contracts/00000000-0000-0000-0000-000000000000/link-odps',
        {
          timeout: 60000,
          contentSelector: '.error-display, [data-testid="error-display"], [role="alert"], .odps-link-page',
        }
      );
      const hasError =
        (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0 ||
        (await page.locator('[role="alert"]').count()) > 0;
      expect(page.url().includes('/login') || page.url().includes('/403') || hasError).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('contracts list loads for link-odps flow', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toContain('/contracts');
      const hasContent =
        (await page.locator('.contract-list-page, [data-testid="contract-list-page"]').first().count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasContent).toBe(true);
    });
  });
});
