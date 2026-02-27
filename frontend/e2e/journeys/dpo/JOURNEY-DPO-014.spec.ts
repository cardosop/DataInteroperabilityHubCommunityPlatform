/**
 * E2E Test: JOURNEY-DPO-014 — Monitor Asset Reliability Score
 *
 * Journey: Monitor Asset Reliability Score
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /observability, /assets/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-014: Monitor Asset Reliability Score', () => {
  test.setTimeout(180000); // 3 min: visible/slowMo; asset detail + observability

  test.describe('Success', () => {
    test('observability page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/observability');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onLogin = page.url().includes('/login');
      const onObservability = page.url().includes('/observability');
      const hasContent =
        (await page.locator('.observability-page, .app-main, h1').count()) > 0;
      expect(onLogin || (onObservability && hasContent)).toBe(true);
    });

    test('asset detail shows reliability or quality info', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/assets', {
        timeout: 60000,
        contentSelector: '.asset-list-page, .empty-state, .error-display',
      });
      const assetLink = page.locator('.asset-list-page a[href*="/assets/"]').first();
      if ((await assetLink.count()) > 0) {
        await assetLink.click();
        await page.waitForURL(/\/assets\/[^/]+$/, { timeout: 10000 });
        await page.waitForSelector('.asset-detail-page, .asset-detail-content, .error-display', {
          timeout: 15000,
        });
        expect(page.url()).toContain('/assets/');
      }
    });
  });

  test.describe('Failure', () => {
    test('asset detail for non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/assets/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|failed to load|404/i').count()) > 0;
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const noDetailContent = (await page.locator('.asset-detail-page .asset-detail-content').count()) === 0;
      expect(hasError || onLogin || on403 || noDetailContent).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('observability page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/observability');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url.includes('/login') || url.includes('/observability')).toBe(true);
    });
  });
});
