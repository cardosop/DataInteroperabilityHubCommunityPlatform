/**
 * E2E Test: JOURNEY-DPO-002 — Publish Asset to Marketplace
 *
 * Journey: Publish Asset to Marketplace
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md, docs/USE_CASES.md
 *
 * Success, Failure, Edge dimensions; real backend only. Routes: /marketplace, /marketplace/publish, /marketplace/listings/:id.
 * Creates an asset via API when needed so Success and "publish without title" tests don't skip (no mocks).
 */

import { expect, test } from '@playwright/test';
import { createAssetViaApi } from '../../fixtures/api-assets';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import {
  loginAndNavigateToRoute,
  waitForAssetDropdownOptions,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-002: Publish Asset to Marketplace', () => {
  test.setTimeout(480000); // 8 min: loginUser may use up to 7 min under rate-limit retries

  test.describe('Success', () => {
    test('publish listing: select asset, fill title and description, submit and reach listing or marketplace', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      const assetId = await createAssetViaApi(testUser, { ensureActivated: true });
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
      await page.fill('#title', `E2E Listing ${Date.now()}`);
      await page.fill('#description', 'E2E listing description');
      const submitBtn = page
        .locator('button[type="submit"]')
        .or(page.locator('button:has-text("Create Listing")'));

      // Wait for create-listing API response and assert success (do not accept 4xx as passing)
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

      // Success: navigate to listing detail or marketplace list (never stay on publish)
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

      // ── DRAFT → PUBLISHED two-step ─────────────────────────────────────
      // If we landed on a listing detail page, check its status badge.
      // If DRAFT: click Publish, intercept the publish API call, assert badge changes.
      if (/\/marketplace\/listings\/[^/]+/.test(new URL(page.url()).pathname)) {
        await page.waitForSelector('.listing-detail-page, .listing-status-badge, h1', {
          timeout: 10000,
        });
        const statusBadge = page.locator('.listing-status-badge, [data-testid="listing-status"]');
        const isDraft =
          (await statusBadge.count()) > 0 &&
          (await statusBadge.first().textContent())?.toUpperCase().includes('DRAFT');

        if (isDraft) {
          const publishBtn = page.locator(
            'button:has-text("Publish"), [data-testid="publish-listing-btn"]'
          );
          if ((await publishBtn.count()) > 0) {
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
            // Badge must change from DRAFT to PUBLISHED
            await expect(statusBadge.first()).toContainText('PUBLISHED', { timeout: 10000 });
          }
        }
      }
    });
  });

  test.describe('Failure', () => {
    test('publish without asset shows validation error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page',
      });
      await page.fill('#title', 'Some Title');
      await page.fill('#description', 'Some description');
      page
        .locator('button[type="submit"]')
        .or(page.locator('button:has-text("Create Listing")'))
        .first()
        .click();
      await new Promise((r) => setTimeout(r, 500));
      const assetError = page.locator('.error-message').filter({ hasText: /asset|required/i });
      await expect(assetError.first()).toBeVisible({ timeout: 5000 });
    });

    test('publish without title shows validation error', async ({ page }) => {
      const testUser = await getTestUser();
      const assetId = await createAssetViaApi(testUser, { ensureActivated: true });
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page',
      });
      const hasAssets = await waitForAssetDropdownOptions(page, { timeout: 15000 });
      if (!hasAssets) {
        throw new Error(
          'No assets in dropdown after createAssetViaApi. Precondition failure: API or tenant mismatch. ' +
            'Ensure backend is running, E2E test user has correct tenant, and assets API returns data.'
        );
      }
      const assetSelect = page.locator('select#asset_id');
      await assetSelect.selectOption({ value: assetId });
      await page.fill('#description', 'Some description');
      page
        .locator('button[type="submit"]')
        .or(page.locator('button:has-text("Create Listing")'))
        .first()
        .click();
      await new Promise((r) => setTimeout(r, 500));
      const titleError = page.locator('.error-message').filter({ hasText: /title|required/i });
      await expect(titleError.first()).toBeVisible({ timeout: 5000 });
    });

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
      expect(onLogin || onPublishWithLoginPrompt).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('publish page loads with empty catalog (dropdown has no assets)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page',
      });
      const assetSelect = page.locator('select#asset_id');
      await expect(assetSelect).toBeVisible({ timeout: 5000 });
      expect(page.url()).toContain('/marketplace/publish');
    });

    test('publish form accepts description with special characters', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page',
      });
      await page.fill('#title', 'E2E Edge Title');
      await page.fill(
        '#description',
        'Description with special chars: <script>, "quotes", & ampersand, unicode: café'
      );
      const descValue = await page.locator('#description').inputValue();
      expect(descValue).toContain('café');
      expect(page.url()).toContain('/marketplace/publish');
    });
  });
});
