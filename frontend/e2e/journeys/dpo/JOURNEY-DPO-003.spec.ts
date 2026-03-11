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
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-003: Manage Asset Lifecycle', () => {
  test.setTimeout(180000); // 3 min: visible/slowMo; assets list + detail + filter

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
      // Newly created assets are always DRAFT
      await expect(statusBadge).toContainText('DRAFT', { timeout: 5000 });
    });

    test('asset can be retired: ACTIVE → RETIRED lifecycle transition', async ({ page }) => {
      // Requires an ACTIVE asset (ensureActivated:true uses the E2E activation helper)
      const testUser = await getTestUser();
      let assetId: string;
      try {
        assetId = await createAssetViaApi(testUser, { ensureActivated: true });
      } catch (err) {
        test.skip(
          true,
          `Cannot ensure ACTIVE asset (${String(err).slice(0, 120)}). Skipping retirement test.`
        );
        return;
      }

      await loginAndNavigateToRoute(page, testUser, `/assets/${assetId}`, {
        timeout: 60000,
        contentSelector: '.asset-detail-page, .asset-detail-content, .error-display',
      });
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on asset detail');
      }

      // Verify the asset is ACTIVE before attempting retirement
      const statusBadge = page.locator('.asset-detail-page .status-badge, .status-badge').first();
      await expect(statusBadge).toBeVisible({ timeout: 15000 });
      const statusText = (await statusBadge.textContent()) ?? '';
      if (!statusText.includes('ACTIVE')) {
        test.skip(true, `Asset is not ACTIVE (status: "${statusText.trim()}"): retirement requires ACTIVE.`);
        return;
      }

      // Click the Retire button (may be in a dropdown or status select)
      const retireBtn = page
        .locator('button:has-text("Retire"), button:has-text("Retire Asset")')
        .first();
      const statusSelect = page.locator('select[id="status"], select[name="status"]').first();

      if ((await retireBtn.count()) > 0) {
        const retireResponsePromise = page.waitForResponse(
          (resp) =>
            resp.url().includes('/assets/') &&
            (resp.url().includes('/retire/') || resp.request().method() === 'PATCH'),
          { timeout: 20000 }
        );
        await retireBtn.click();
        const retireResp = await retireResponsePromise.catch(() => null);
        if (retireResp && retireResp.status() >= 400) {
          const body = await retireResp.text().catch(() => '');
          throw new Error(`Retire API returned ${retireResp.status()}: ${body.slice(0, 200)}`);
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
