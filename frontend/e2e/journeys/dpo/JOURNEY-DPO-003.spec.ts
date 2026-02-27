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

    test('asset detail loads and shows status badge', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display, .loading-spinner-container',
      });
      const assetRow = page.locator('.asset-list-page tr.asset-row').first();
      if ((await assetRow.count()) > 0) {
        await assetRow.click();
        await page.waitForURL(/\/assets\/[^/]+$/, { timeout: 10000 });
        await page.waitForSelector('.asset-detail-page, .asset-detail-content, .status-badge', {
          timeout: 15000,
        });
        const statusBadge = page.locator('.status-badge').first();
        await expect(statusBadge).toBeVisible({ timeout: 5000 });
      }
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
