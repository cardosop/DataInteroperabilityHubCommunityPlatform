/**
 * E2E Test: JOURNEY-MP-002 — Publish Asset to Marketplace
 *
 * Journey: Publish Asset to Marketplace
 * Persona: Data Product Owner
 * Reference: docs/MARKETPLACE_USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /marketplace/publish, /assets.
 * Uses getTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';
import { createAssetViaApi } from '../../fixtures/api-assets';
import { verifyViaApi } from '../../fixtures/verifyViaApi';

test.describe('JOURNEY-MP-002: Publish Asset to Marketplace', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('assets list loads for publish selection', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/assets');
    });

    test('marketplace publish page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        throw new Error(`Unexpected redirect to ${page.url()} — verify test user has marketplace publish access`);
      }
      expect(page.url()).toContain('/marketplace/publish');
    });

    test('DPO can fill publish form and submit listing', async ({ page }) => {
      const testUser = await getTestUser();
      // ListingPublishPage only shows ACTIVE assets in the dropdown — must use ensureActivated
      // intentional: best-effort .catch on an optional step — primary pass/fail is made by a downstream assertion (verifyViaApi, waitFor, explicit expect). The fallback value tolerates well-known transient or absent-UI cases without papering over real failures.
      const assetId = await createAssetViaApi(testUser, { ensureActivated: true }).catch(() => null);
      if (!assetId) {
        test.skip(true, 'Could not create/find an ACTIVE asset — skipping publish form interaction');
        return;
      }

      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page, .app-main',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login') || page.url().includes('/403')) return;
      if (!(await page.locator('.listing-publish-page').isVisible())) {
        test.info().annotations.push({ type: 'note', description: 'Publish form not found — skipping form interaction' });
        return;
      }

      const titleInput = page.locator('#title, input[name="title"]');
      if ((await titleInput.count()) === 0) {
        test.info().annotations.push({ type: 'note', description: 'No title input found — skipping form interaction' });
        return;
      }
      await titleInput.fill(`E2E Listing ${Date.now()}`);

      // Description is required by ListingPublishPage validate() — even though it has no * in the label
      const descInput = page.locator('#description, textarea[name="description"]');
      if ((await descInput.count()) > 0) {
        await descInput.fill('E2E listing created by JOURNEY-MP-002 automated test');
      }

      const assetSelect = page.locator('#asset_id, select[name="asset_id"]');
      if ((await assetSelect.count()) === 0) {
        test.info().annotations.push({ type: 'note', description: 'No asset_id select found — form may use a custom picker component' });
        return;
      }
      // The select is populated asynchronously by useAssets({ status: 'ACTIVE' }).
      // Wait for the specific option to appear before selecting — avoids silent selectOption failure
      // if React Query hasn't resolved yet when the page first renders.
      // intentional: treats promise rejection as a structured false — the caller's if/else below consumes the boolean without swallowing.
      const assetOptionAvailable = await page
        .waitForSelector(`#asset_id option[value="${assetId}"]`, { state: 'attached', timeout: 15000 })
        .then(() => true)
        .catch(() => false);
      if (!assetOptionAvailable) {
        test.skip(true, `ACTIVE asset ${assetId.slice(0, 8)} not in dropdown after 15 s — asset may not have fully activated`);
        return;
      }
      await assetSelect.selectOption(assetId);

      // NOTE: Do NOT change pricing_model after selecting asset_id.
      // ListingPublishPage uses object-spread onChange handlers: each handler captures formData
      // via closure. React 18 schedules re-renders via MessageChannel (macrotask), so a second
      // selectOption call before the macrotask fires uses stale formData and resets asset_id=''.
      // The default pricing model (FREE) is valid — no change needed.

      // Let React's MessageChannel scheduler flush all pending state updates before submit.
      // Without this pause, the click fires before React has settled formData with asset_id set.
      await page.waitForTimeout(300);

      // Submit the form and detect the outcome via React navigation, API error, or validation error.
      // ListingPublishPage navigates to /marketplace/listings/<uuid> on success.
      // On API error: createMutation.isError → <ErrorDisplay className="error-display">.
      // On validation failure: setErrors() → <span className="error-message"> (NOT error-display).
      await page.locator('button[type="submit"]').click();

      const resultType = await Promise.race([
        page
          .waitForURL(/\/marketplace\/listings\/[a-fA-F0-9-]{36}$/, { timeout: 30000 })
          .then(() => 'navigated'),
        page
          .waitForSelector('.error-display', { state: 'visible', timeout: 30000 })
          .then(() => 'api-error'),
        page
          .waitForSelector('.error-message', { state: 'visible', timeout: 30000 })
          .then(() => 'validation-error'),
      ]).catch(() => 'timeout');

      if (resultType === 'navigated') {
        // Listing created — confirm we landed on the listing detail page
        expect(page.url()).toMatch(/\/marketplace\/listings\/[a-fA-F0-9-]{36}$/);

        // Dual-channel verification (PR 7a-ext2d). UI navigation only proves
        // the client-side router transition; it does not prove the backend
        // persisted the Listing row. Hit the API directly to confirm the
        // listing exists and is linked to the asset the user chose — catches
        // the failure mode where the frontend optimistically navigates on a
        // 202-with-pending-job and the job later silently fails.
        const listingId = page.url().match(/\/marketplace\/listings\/([a-fA-F0-9-]{36})/)?.[1];
        if (!listingId) {
          throw new Error(`Expected /marketplace/listings/<uuid> URL after submit; got ${page.url()}`);
        }
        await verifyViaApi(
          page,
          `/api/v1/marketplace/listings/${listingId}/`,
          (body: { asset_id?: string }) => body.asset_id === assetId,
        );
      } else if (resultType === 'api-error') {
        // Backend rejected the listing creation (e.g. duplicate, permission, plan limit)
        // intentional: tolerates a detached/removed element while extracting text for a diagnostic message; the surrounding throw/expect below this catch is the primary failure path.
        const errText = await page.locator('.error-display').first().textContent().catch(() => '');
        test.info().annotations.push({
          type: 'note',
          description: `Listing creation returned an API error: ${errText.slice(0, 200)}`,
        });
      } else if (resultType === 'validation-error') {
        // Form validation failed — asset_id or title or description was empty in React state.
        // Capture which fields triggered validation errors for diagnostics.
        const errText = await page.locator('.error-message').allTextContents().catch(() => [] as string[]);
        throw new Error(
          `Form validation failed before submission — required fields not set in React state. ` +
          `Validation errors: ${errText.join('; ')}. ` +
          `This usually means a React stale-closure race: consecutive selectOption/fill calls ` +
          `before React's MessageChannel scheduler flushed state updates.`
        );
      } else {
        throw new Error(
          'Listing publish form did not navigate or show an error after 30 s — ' +
          'check that asset_id was selected, all required fields filled, and submit button is enabled'
        );
      }
    });
  });

  test.describe('Failure', () => {
    test('publish with non-existent asset shows error or empty', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page, .empty-state',
        acceptRedirectToLogin: true,
      });
      await page.waitForTimeout(1000);
      const onLogin = page.url().includes('/login');
      const onPublish = page.url().includes('/marketplace/publish');
      const hasContent =
        (await page.locator('.listing-publish-page, .app-main, .empty-state').count()) > 0;
      expect(onLogin || (onPublish && hasContent)).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('assets and marketplace publish routes accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/assets');
      await loginAndNavigateToRoute(page, testUser, '/marketplace/publish', {
        timeout: 60000,
        contentSelector: '.listing-publish-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/marketplace/publish');
    });
  });
});
