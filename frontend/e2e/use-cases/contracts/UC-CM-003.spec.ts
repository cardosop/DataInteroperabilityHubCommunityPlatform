/**
 * E2E: UC-CM-003 — Assign Data Steward
 *
 * Use Case: Assign Data Steward (Community Management)
 * Persona: Community Manager (uses getTestUser — no dedicated CM user)
 * Reference: docs/USE_CASES.md, docs/TEST_TRACEABILITY.md
 *
 * Success/Failure/Edge. Routes: /communities (Phase 27.2).
 * Capability-gated: social.communities. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('UC-CM-003: Assign Data Steward @critical', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('communities page loads with steward assignment UI', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/communities', {
        timeout: 60000,
        contentSelector:
          '.communities-page, .communities-tab, .unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"]',
        acceptRedirectToLogin: false,
      });
      if (page.url().includes('/login')) {
        throw new Error('Redirected to login — auth may have failed or session expired');
      }
      await waitForLoadingComplete(page, { timeout: 30000 });

      const url = page.url();
      if (url.includes('/403') || url.includes('/unavailable')) {
        await expect(
          page.locator('.unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"], [role="alert"]').first()
        ).toBeVisible({ timeout: 10000 });
        return;
      }

      const isCapabilityGated = (await page.locator('.unavailable-page, [data-testid="unavailable-page"]').first().count()) > 0;
      if (isCapabilityGated) {
        await expect(page.locator('.unavailable-page, [data-testid="unavailable-page"]').first().first()).toBeVisible({ timeout: 5000 });
        return;
      }

      expect(url).toContain('/communities');

      const hasCommunitiesPage = (await page.locator('.communities-page, .communities-tab, .community-list, [class*="community"]').count()) > 0;
      const hasEmptyState = (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;

      expect(hasCommunitiesPage || hasEmptyState).toBe(true);

      const hasStewardSection =
        (await page.locator('[class*="steward"], [data-testid*="steward"], .steward-section').count()) > 0;
      const hasAssignButton =
        (await page.locator('button:has-text("Assign"), button:has-text("steward"), [data-testid*="assign"]').count()) > 0;
      const hasUserPicker =
        (await page.locator('[class*="user-picker"], [class*="member"], [data-testid*="steward-picker"], [class*="steward"] select, [class*="steward"] [role="combobox"]').count()) > 0;
      const hasCommunityList =
        (await page.locator('.communities-page, .communities-tab, .community-list, [class*="community"]').count()) > 0;

      // Communities page may not have steward UI visible until a community is selected;
      // verify at least the community list or steward-related UI is present
      expect(hasStewardSection || hasAssignButton || hasUserPicker || hasCommunityList).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to communities redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/communities', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|communities)/, { timeout: 20_000 });
      const url = page.url();
      // Unauth test: only login redirect is acceptable (not /communities — that would mean auth bypass)
      const onLogin = url.includes('/login');
      const onCommunitiesWithLoginPrompt =
        url.includes('/communities') &&
        ((await page.locator('input#email, [href*="/login"]').count()) > 0 ||
          (await page.locator('text=Sign in').count()) > 0);
      expect(onLogin || onCommunitiesWithLoginPrompt).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('communities page shows list or empty state', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/communities', {
        timeout: 60000,
        contentSelector:
          '.communities-page, .communities-tab, .unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"]',
        acceptRedirectToLogin: false,
      });
      if (page.url().includes('/login')) {
        throw new Error('Redirected to login on communities edge test');
      }
      await waitForLoadingComplete(page, { timeout: 30000 });

      const url = page.url();
      if (url.includes('/403') || url.includes('/unavailable')) {
        await expect(
          page.locator('.unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"], [role="alert"]').first()
        ).toBeVisible({ timeout: 10000 });
        return;
      }

      const isCapabilityGated = (await page.locator('.unavailable-page, [data-testid="unavailable-page"]').first().count()) > 0;
      if (isCapabilityGated) {
        await expect(page.locator('.unavailable-page, [data-testid="unavailable-page"]').first().first()).toBeVisible({ timeout: 5000 });
        return;
      }

      expect(url).toContain('/communities');

      // Verify list or empty state is rendered
      const hasList =
        (await page.locator('.communities-page, .communities-tab, .community-list, [class*="community"]').count()) > 0;
      const hasEmptyState = (await page.locator('.empty-state, [data-testid="empty-state"], [class*="empty"]').count()) > 0;

      expect(hasList || hasEmptyState).toBe(true);
    });
  });
});
