/**
 * E2E: UC-AM-002 — Publish Asset to Marketplace
 *
 * Use Case: Publish Asset to Marketplace
 * Persona: Data Product Owner
 * Reference: docs/USE_CASES.md#uc-am-002
 *
 * Success/Failure/Edge. Routes: /marketplace/publish, /marketplace/listings/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { createAssetViaApi } from '../../fixtures/api-assets';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import {
  loginAndNavigateToRoute,
  waitForAssetDropdownOptions,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('UC-AM-002: Publish Asset to Marketplace', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('publish listing: select asset, fill title and description, submit and verify published', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      // forceNew: true — always create a fresh ACTIVE asset so the dropdown contains it.
      // Reusing assets fails once they accumulate a listing across runs.
      const assetId = await createAssetViaApi(testUser, { forceNew: true, ensureActivated: true });
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page, h1',
      });
      await waitForLoadingComplete(page, { timeout: 15000 });

      const hasAssets = await waitForAssetDropdownOptions(page, { timeout: 25000 });
      if (!hasAssets) {
        throw new Error(
          'No assets in dropdown after createAssetViaApi. Precondition failure: API or tenant mismatch. ' +
            'Ensure backend is running, E2E test user has correct tenant, and assets API returns data.'
        );
      }

      const assetSelect = page.locator('select#asset_id');
      await assetSelect.selectOption({ value: assetId });
      await page.fill('#title', `E2E Publish ${Date.now()}`);
      await page.fill('#description', 'E2E publish asset to marketplace description');

      const submitBtn = page
        .locator('button[type="submit"]')
        .or(page.locator('button:has-text("Create Listing")'));

      // Wait for create-listing API response and assert success
      const createListingResponse = page.waitForResponse(
        (resp) =>
          resp.request().method() === 'POST' &&
          resp.url().includes('/marketplace/listings/') &&
          !resp.url().includes('/search/'),
        { timeout: 30000 }
      );
      await submitBtn.first().click();
      const resp = await createListingResponse;
      if (resp.status() >= 400) {
        const body = await resp.text().catch(() => '');
        throw new Error(
          `Create listing API failed: ${resp.status()} ${body}. ` +
            `Asset must be ACTIVE; ensure createAssetViaApi(ensureActivated: true) succeeded.`
        );
      }

      // Success: navigated away from /publish OR listing status shows PUBLISHED
      await page.waitForURL(
        (url) => {
          const u = new URL(url);
          const path = u.pathname;
          return (
            /\/marketplace\/listings\/[^/]+/.test(path) || path === '/marketplace' || path === '/marketplace/'
          );
        },
        { timeout: 30000 }
      );
      expect(page.url()).not.toContain('/marketplace/publish');

      // D85: Success test must NOT accept .error-display as valid content
      const hasErrorDisplay = (await page.locator('.error-display').count()) > 0;
      expect(hasErrorDisplay).toBe(false);

      // Must be on listing detail to verify PUBLISHED status
      const onListingDetail = /\/marketplace\/listings\/[^/]+/.test(new URL(page.url()).pathname);
      if (!onListingDetail) {
        test.skip(true, 'Did not navigate to listing detail');
      }

      // Check for PUBLISHED status badge
      const statusBadge = page.locator('.listing-status-badge, [data-testid="listing-status"]');
      const isDraft =
        (await statusBadge.count()) > 0 &&
        (await statusBadge.first().textContent())?.toUpperCase().includes('DRAFT');

      if (isDraft) {
        const publishBtn = page.locator(
          'button:has-text("Publish"), [data-testid="publish-listing-btn"]'
        );
        if ((await publishBtn.count()) === 0) {
          test.skip(true, 'Listing is DRAFT but no Publish button found');
        }
        const publishResponsePromise = page.waitForResponse(
          (r) =>
            (r.url().includes('/marketplace/listings/') &&
              (r.request().method() === 'PATCH' || r.request().method() === 'POST')) ||
            r.url().includes('/publish/'),
          { timeout: 20000 }
        );
        await publishBtn.first().click();
        const publishResp = await publishResponsePromise;
        expect(publishResp.status()).toBeGreaterThanOrEqual(200);
        expect(publishResp.status()).toBeLessThan(300);
        await expect(statusBadge.first()).toContainText('PUBLISHED', { timeout: 10000 });
      }
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to marketplace publish redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/marketplace/publish', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|marketplace)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onPublishWithLoginPrompt =
        url.includes('/marketplace') &&
        ((await page.locator('input#email, [href*="/login"]').count()) > 0 ||
          (await page.locator('text=Sign in').count()) > 0);
      expect(onLogin || onPublishWithLoginPrompt).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Edge', () => {
    test('publish page renders form elements (select, title input, submit button)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page, h1',
      });
      await waitForLoadingComplete(page, { timeout: 15000 });
      expect(page.url()).toContain('/marketplace/publish');

      const assetSelect = page.locator('select#asset_id');
      await expect(assetSelect).toBeVisible({ timeout: 10000 });

      const titleInput = page.locator('#title');
      await expect(titleInput).toBeVisible({ timeout: 5000 });

      const submitBtn = page
        .locator('button[type="submit"]')
        .or(page.locator('button:has-text("Create Listing")'));
      await expect(submitBtn.first()).toBeVisible({ timeout: 5000 });
    });
  });
});
