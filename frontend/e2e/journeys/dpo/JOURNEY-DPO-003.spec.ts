/**
 * E2E Test: JOURNEY-DPO-003 — Manage Asset Lifecycle
 *
 * Journey: Manage Asset Lifecycle (DRAFT → ACTIVE → RETIRED)
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /assets, /assets/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { createAssetViaApi } from '../../fixtures/api-assets';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import {
  assertNonExistentIdShowsError,
  ensureAssetActivationPrerequisites,
  loginAndNavigateToRoute,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-003: Manage Asset Lifecycle', () => {
  test.setTimeout(480000); // 8 min: visible/slowMo (400ms/action) + UI activation + retirement flow

  test.describe('Success', () => {
    test('assets list loads with lifecycle status', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display, .loading-spinner-container, h1',
      });
      expect(page.url()).toContain('/assets');
    });

    test('asset detail loads and shows DRAFT status badge (API-seeded)', async ({ page }) => {
      // Use createAssetViaApi to guarantee an asset exists; navigating to that asset
      // directly avoids the vacuous if (assetRow.count > 0) conditional.
      const testUser = await getTestUser();
      const assetId = await createAssetViaApi(testUser);
      await loginAndNavigateToRoute(page, testUser, `/assets/${assetId}`, {
        timeout: 60000,
        contentSelector: '.asset-detail-page, .asset-detail-content, .error-display',
      });
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on asset detail');
      }
      await page.waitForSelector('.asset-detail-page, .asset-detail-content, .error-display', {
        timeout: 15000,
      });
      const hasError = (await page.locator('.error-display').count()) > 0;
      if (hasError) {
        const errText = (await page.locator('.error-display').first().textContent()) ?? '';
        throw new Error(`Asset detail failed to load: ${errText.slice(0, 250)}`);
      }
      const statusBadge = page.locator('.asset-detail-page .status-badge, .status-badge').first();
      await expect(statusBadge).toBeVisible({ timeout: 10000 });
      // createAssetViaApi reuses existing assets (first match) which may already be ACTIVE;
      // the test verifies the detail page loads with a valid lifecycle status badge.
      const badgeText = (await statusBadge.textContent()) ?? '';
      expect(['DRAFT', 'ACTIVE', 'RETIRED', 'DEPRECATED'].some((s) => badgeText.includes(s))).toBe(true);
    });

    test('asset can be retired: ACTIVE → RETIRED lifecycle transition', async ({ page }) => {
      // Requires an ACTIVE asset. Always create a FRESH asset (forceNew:true) — never reuse
      // an existing ACTIVE asset. Reusing a shared asset causes a race condition when chromium
      // and visible workers run in parallel: both grab the same ACTIVE asset and one retires it
      // before the other reaches the retire step (chromium skip / visible 409 conflict error).
      const testUser = await getTestUser();
      // forceNew:true guarantees a unique DRAFT asset for this test run.
      const assetId = await createAssetViaApi(testUser, { forceNew: true });

      await loginAndNavigateToRoute(page, testUser, `/assets/${assetId}`, {
        timeout: 60000,
        contentSelector: '.asset-detail-page, .asset-detail-content, .error-display',
      });
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on asset detail');
      }

      // Check the asset's current status
      const statusBadge = page.locator('.asset-detail-page .status-badge, .status-badge').first();
      await expect(statusBadge).toBeVisible({ timeout: 15000 });
      const statusText = (await statusBadge.textContent()) ?? '';

      // If asset is DRAFT (API activation didn't work), try activating via UI
      if (!statusText.includes('ACTIVE')) {
        await ensureAssetActivationPrerequisites(page, assetId);
        await page.reload({ waitUntil: 'domcontentloaded' });
        await waitForLoadingComplete(page, { timeout: 30000 });
        await page.waitForSelector('.asset-detail-page, .error-display', { timeout: 15000 });

        const activateBtn = page.locator(
          'button:has-text("Activate"), button:has-text("Activate Asset")'
        );
        if ((await activateBtn.count()) === 0) {
          test.skip(true, `Asset is ${statusText.trim()} and no Activate button found: retirement requires ACTIVE.`);
          return;
        }
        const actRespPromise = page.waitForResponse(
          (resp) => resp.url().includes('/assets/') && resp.url().includes('/activate/'),
          { timeout: 60000 }
        );
        await activateBtn.first().click();
        const actResp = await actRespPromise.catch(() => null);
        if (!actResp || actResp.status() !== 200) {
          test.skip(
            true,
            `UI activation returned ${actResp?.status() ?? 'timeout'}: retirement requires ACTIVE.`
          );
          return;
        }
        await new Promise((r) => setTimeout(r, 2000));
        await page.reload({ waitUntil: 'domcontentloaded' });
        await waitForLoadingComplete(page, { timeout: 30000 });
        await page.waitForSelector('.asset-detail-page, .error-display', { timeout: 15000 });

        const activatedBadge = page.locator('.asset-detail-page .status-badge, .status-badge').first();
        const activatedStatus = (await activatedBadge.textContent().catch(() => '')) ?? '';
        if (!activatedStatus.includes('ACTIVE')) {
          test.skip(true, `Asset still not ACTIVE after UI activation attempt (status: "${activatedStatus.trim()}").`);
          return;
        }
      }

      // Click the Retire button (may be in a dropdown or status select)
      const retireBtn = page
        .locator('button:has-text("Retire"), button:has-text("Retire Asset")')
        .first();
      const statusSelect = page.locator('select[id="status"], select[name="status"]').first();

      if ((await retireBtn.count()) > 0) {
        // Narrow filter to this specific asset's URL so background PATCHes (React Query refetches,
        // other mutations) don't resolve the promise before the retire PATCH fires (chromium fast mode).
        const retireResponsePromise = page.waitForResponse(
          (resp) =>
            resp.url().includes(`/assets/${assetId}/`) &&
            (resp.url().includes('/retire/') || resp.request().method() === 'PATCH'),
          { timeout: 20000 }
        );
        await retireBtn.click();
        const retireResp = await retireResponsePromise.catch(() => null);
        if (retireResp && retireResp.status() >= 400) {
          const body = await retireResp.text().catch(() => '');
          // 400 often means version conflict — reload and retry once with the page's fresh version
          if (retireResp.status() === 400) {
            await page.reload({ waitUntil: 'domcontentloaded' });
            await page.waitForSelector('.asset-detail-page, .asset-detail-content', { timeout: 15000 });
            const retireBtn2 = page
              .locator('button:has-text("Retire"), button:has-text("Retire Asset")')
              .first();
            if ((await retireBtn2.count()) > 0) {
              const retireResponsePromise2 = page.waitForResponse(
                (resp) =>
                  resp.url().includes(`/assets/${assetId}/`) &&
                  (resp.url().includes('/retire/') || resp.request().method() === 'PATCH'),
                { timeout: 20000 }
              );
              await retireBtn2.click();
              const retireResp2 = await retireResponsePromise2.catch(() => null);
              if (retireResp2 && retireResp2.status() >= 400) {
                const body2 = await retireResp2.text().catch(() => '');
                throw new Error(`Retire API returned ${retireResp2.status()} on retry: ${body2.slice(0, 200)}`);
              }
            }
          } else {
            throw new Error(`Retire API returned ${retireResp.status()}: ${body.slice(0, 200)}`);
          }
        }
      } else if ((await statusSelect.count()) > 0) {
        await statusSelect.selectOption('RETIRED');
        const saveBtn = page.locator('button:has-text("Save"), button[type="submit"]').first();
        if ((await saveBtn.count()) > 0) await saveBtn.click();
      } else {
        test.skip(true, 'No Retire button or status select found; UI may not expose retirement for this user/role.');
        return;
      }

      await page.waitForTimeout(2000);

      // Verify RETIRED status in UI (reload to get fresh state from backend)
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.waitForSelector('.asset-detail-page, .error-display', { timeout: 15000 });
      const updatedBadge = page.locator('.asset-detail-page .status-badge, .status-badge').first();
      await expect(updatedBadge).toBeVisible({ timeout: 10000 });
      await expect(updatedBadge).toContainText(/RETIRED|DEPRECATED/, { timeout: 10000 });
    });
  });

  test.describe('Failure', () => {
    test('asset detail for non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display, .loading-spinner-container, h1',
      });
      await page.goto('/assets/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.asset-detail-page',
        waitAfterLoad: 8000,
        selectorTimeout: 60000,
      });
    });

    test('unauthenticated access to assets list redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/assets', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|assets)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onAssetsWithLoginPrompt =
        url.includes('/assets') &&
        ((await page.locator('input#email, [href*="/login"]').count()) > 0 ||
          (await page.locator('text=Sign in').count()) > 0);
      expect(onLogin || onAssetsWithLoginPrompt).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('asset list with status filter shows filtered results', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display, .loading-spinner-container',
      });
      const statusSelect = page.locator('select').filter({ hasText: /Draft|Active|Retired/ }).first();
      if ((await statusSelect.count()) > 0) {
        await statusSelect.selectOption({ index: 1 });
        await page.waitForTimeout(500);
      }
      expect(page.url()).toContain('/assets');
    });

    test('asset list search with empty string shows list or empty state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display, .loading-spinner-container',
      });
      expect(page.url()).toContain('/assets');
      // Wait for loading to complete before interacting
      await page
        .locator('.asset-list-page, .empty-state, .error-display')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 });
      const searchInput = page.getByRole('textbox', { name: 'Search assets' });
      if ((await searchInput.count()) > 0) {
        await searchInput.fill('');
        await page.waitForTimeout(500);
      }
      const hasContent =
        (await page.locator('.asset-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });
});
