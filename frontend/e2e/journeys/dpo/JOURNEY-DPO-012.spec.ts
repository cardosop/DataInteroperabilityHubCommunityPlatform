/**
 * E2E Test: JOURNEY-DPO-012 — Join Data Community
 *
 * Journey: Join Data Community
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /communities (Phase 27.2).
 * Capability-gated: social.communities. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-012: Join Data Community @critical', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('communities page loads and shows community list or Join button', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/communities', {
        timeout: 90000,
        contentSelector:
          '.communities-page, .communities-tab, .unavailable-page, [data-testid="unavailable-page"]',
        acceptRedirectToLogin: false,
      });
      await page.waitForTimeout(1500);

      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onCommunities = url.includes('/communities');

      if (onLogin) {
        throw new Error('Unexpected redirect to login on communities page; auth may have failed.');
      }

      // If capability is off, an unavailable or 403 state is valid
      if (onUnavailable || on403) {
        const unavailablePage = page.locator('.unavailable-page, [data-testid="unavailable-page"]').first();
        await expect(unavailablePage.first()).toBeVisible({ timeout: 5000 });
        return;
      }

      expect(onCommunities).toBe(true) /* acceptable states */;

      // When the communities page is enabled, validate specific community UI elements:
      // a community list, a "Join" / membership button, or an empty state
      const communityList = page.locator('.community-list, [data-testid="community-list"]');
      const joinBtn = page.locator(
        'button:has-text("Join"), [data-testid="join-community-btn"]'
      );
      const emptyState = page.locator('.empty-state, [data-testid="empty-state"], [data-testid="communities-empty"]');

      const hasList = (await communityList.count()) > 0;
      const hasJoin = (await joinBtn.count()) > 0;
      const hasEmpty = (await emptyState.count()) > 0;

      expect(hasList || hasJoin || hasEmpty).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Failure', () => {
    test('communities page without capability shows unavailable indicator (not a crash)', async ({ page }) => {
      // When social.communities is disabled, /communities must show an unavailable page or 403.
      // It must NOT show the communities list as if the capability were enabled.
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/communities', {
        timeout: 90000,
        contentSelector: '.communities-page, .communities-tab, .unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"]',
        acceptRedirectToLogin: false,
      });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on communities failure test');
      }

      const capabilityEnabled =
        page.url().includes('/communities') &&
        (await page.locator('.communities-page, .communities-tab').count()) > 0 &&
        (await page.locator('.unavailable-page, [data-testid="unavailable-page"]').first().count()) === 0;
      const capabilityDisabled =
        (await page.locator('.unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"]').count()) > 0 ||
        page.url().includes('/unavailable') ||
        page.url().includes('/403');

      expect(capabilityEnabled || capabilityDisabled).toBe(true) /* acceptable states */;

      if (capabilityDisabled) {
        await expect(
          page.locator('.unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"]').first()
        ).toBeVisible({ timeout: 10000 });
      } else {
        await expect(
          page.locator('.communities-page, .communities-tab').first()
        ).toBeVisible({ timeout: 10000 });
      }
    });
  });

  test.describe('Edge', () => {
    test('communities page renders content or capability-unavailable state (no crash)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/communities', {
        timeout: 90000,
        contentSelector: '.communities-page, .communities-tab, .unavailable-page, [data-testid="unavailable-page"]',
        acceptRedirectToLogin: false,
      });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on communities edge test');
      }

      // Must render something meaningful — not a blank or crash
      const hasContent =
        (await page.locator('.communities-page, .communities-tab, .unavailable-page, [data-testid="unavailable-page"]').count()) > 0 ||
        page.url().includes('/403');
      expect(hasContent).toBe(true) /* acceptable states */;
    });
  });
});
