/**
 * E2E Test: JOURNEY-DPO-017 — Export ODPS Product
 *
 * Journey: Export ODPS Product
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /odps/:id, /contracts/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { createODPSProductViaApi } from '../../fixtures/api-assets';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-017: Export ODPS Product', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('ODPS detail page loads and export button is accessible (API-seeded)', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      const odpsContractId = await createODPSProductViaApi(testUser);

      await loginAndNavigateToRoute(page, testUser, `/odps/${odpsContractId}`, {
        timeout: 60000,
        contentSelector: '.odps-detail-main, .odps-detail-page, .error-display',
      });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on ODPS detail page');
      }

      const hasError = (await page.locator('.error-display').count()) > 0;
      if (hasError) {
        const errText = (await page.locator('.error-display').first().textContent()) ?? '';
        throw new Error(`ODPS detail page failed to load: ${errText.slice(0, 250)}`);
      }

      await expect(
        page.locator('.odps-detail-main, .odps-detail-page').first()
      ).toBeVisible({ timeout: 10000 });

      expect(page.url()).toMatch(/\/odps\/[^/]+$/);

      const exportBtn = page.locator(
        'button:has-text("Export"), button:has-text("Download"), a:has-text("Export"), a:has-text("Download")'
      );
      await expect(exportBtn.first()).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Failure', () => {
    test('ODPS detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      // Use loginAndNavigateToRoute to ensure auth tokens survive navigation.
      // ODPSDetailPage checks error state BEFORE loading skeleton, so ErrorDisplay
      // with role="alert" renders immediately on 404.
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/odps/00000000-0000-0000-0000-000000000000',
        {
          timeout: 60000,
          contentSelector: '.error-display, .odps-detail-page, [role="alert"]',
        }
      );

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login when navigating to non-existent ODPS detail');
      }

      const hasExplicitError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('[role="alert"]').count()) > 0;
      expect(hasExplicitError).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('ODPS list with empty state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/odps', {
        timeout: 60000,
        contentSelector: '.odps-list-page, .odps-empty-state, .error-display',
      });
      test.skip(page.url().includes('/login'), 'Redirected to login');
      expect(page.url()).toContain('/odps');
      const hasContent =
        (await page.locator('.odps-list-page, .odps-empty-state, .empty-state').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });
});
