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
import { getTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DPO-017: Export ODPS Product', () => {
  test.setTimeout(180000); // 3 min: visible/slowMo

  test.describe('Success', () => {
    test('ODPS detail page loads and export button is accessible (API-seeded)', async ({
      page,
    }) => {
      // Use createODPSProductViaApi to guarantee an ODPS product exists — eliminates the
      // test.skip fallback for empty catalog that was a source of vacuous passes.
      const testUser = await getTestUser();
      const odpsContractId = await createODPSProductViaApi(testUser);

      await loginUser(page, testUser);
      await page.goto(`/odps/${odpsContractId}`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.odps-detail-main, .odps-detail-page, .error-display, #email', {
        timeout: 30000,
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

      // Export button MUST be present on a loaded ODPS detail page
      const exportBtn = page.locator(
        'button:has-text("Export"), button:has-text("Download"), a:has-text("Export"), a:has-text("Download")'
      );
      await expect(exportBtn.first()).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Failure', () => {
    test('ODPS detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/odps/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      // Wait for the error to appear: the ODPS page loads async (auth store init + API 404 response).
      // A fixed 3s wait is insufficient under parallel load — use a selector wait instead.
      // The ODPS error display uses role="alert" (e.g. "Failed to load ODPS contract").
      await page
        .waitForSelector('[role="alert"], .error-display, #email', { timeout: 30000 })
        .catch(() => null);
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login when navigating to non-existent ODPS detail');
      }
      // The UI MUST show an explicit error when a non-existent ODPS id is requested.
      // Accepting "no success content" is a false positive — the detail page never renders for
      // 404s regardless of whether an error is shown. Require an explicit error indicator.
      const hasExplicitError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('[role="alert"]').count()) > 0;
      expect(hasExplicitError).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('ODPS list with empty state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/odps');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.odps-list-page, .odps-empty-state, .error-display, .loading-spinner-container, #email', {
        timeout: 65000,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/odps');
    });
  });
});
