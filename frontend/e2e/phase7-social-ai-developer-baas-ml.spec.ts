/**
 * E2E Test: Phase 7 — Social + AI + Developer/BaaS + ML (capability-gated) — DEPRECATED (journey-aligned)
 *
 * EXCLUDED FROM CI: removed from batch 7 (2026-03-14). Run manually via: bash scripts/e2e-batches.sh 9
 * Content maps to: JOURNEY-DC-008, JOURNEY-DPO-009, JOURNEY-DC-006, JOURNEY-DPO-007, JOURNEY-DEV-001/009,
 * BaaS, JOURNEY-DS-003. Prefer journey specs under journeys/dc/, journeys/dpo/, journeys/dev/, etc.
 * Deletion target: after sign-off. Backend-not-implemented (e.g. UC-SOCIAL-005): assert /unavailable.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from './fixtures/auth';
import { loginAndNavigateToRoute } from './fixtures/helpers';

test.describe('Phase 7 — Social + AI + Developer/BaaS + ML', () => {
  test.beforeEach(() => {
    test.setTimeout(90000);
  });

  test('Communities page loads or shows clear gated message', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/communities', {
      timeout: 60000,
      contentSelector: '.communities-page, .communities-tab, .unavailable-page',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const communitiesPage = page.locator('.communities-page, .communities-tab');
    const unavailablePage = page.locator('.unavailable-page');
    const hasCommunitiesContent = (await communitiesPage.count()) > 0;
    const hasUnavailable = (await unavailablePage.count()) > 0;

    expect(hasCommunitiesContent || hasUnavailable).toBe(true) /* acceptable states */;
    if (hasUnavailable) {
      await expect(unavailablePage).toContainText(/unavailable|not available|contact/i);
    }
    if (hasCommunitiesContent) {
      await expect(communitiesPage.locator('h2, h1')).toContainText(/Communities|Data Communities/i);
    }
  });

  test('AI Search page loads or shows clear gated message', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/ai/search', {
      timeout: 60000,
      contentSelector: '.ai-search-page, .unavailable-page',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const aiPage = page.locator('.ai-search-page');
    const unavailablePage = page.locator('.unavailable-page');
    const hasAIContent = (await aiPage.count()) > 0;
    const hasUnavailable = (await unavailablePage.count()) > 0;

    expect(hasAIContent || hasUnavailable).toBe(true) /* acceptable states */;
    if (hasUnavailable) {
      await expect(unavailablePage).toContainText(/unavailable|not available|contact/i);
    }
    if (hasAIContent) {
      await expect(aiPage.locator('h1')).toContainText(/AI|Natural Language|Search/i);
    }
  });

  test('Developer portal page loads or shows clear gated message', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/developer', {
      timeout: 60000,
      contentSelector: '.developer-portal-page, .unavailable-page',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const devPage = page.locator('.developer-portal-page');
    const unavailablePage = page.locator('.unavailable-page');
    const hasDevContent = (await devPage.count()) > 0;
    const hasUnavailable = (await unavailablePage.count()) > 0;

    expect(hasDevContent || hasUnavailable).toBe(true) /* acceptable states */;
    if (hasUnavailable) {
      await expect(unavailablePage).toContainText(/unavailable|not available|contact/i);
    }
    if (hasDevContent) {
      await expect(devPage.locator('h1')).toContainText(/Developer|Portal/i);
    }
  });

  test('BaaS page loads or shows clear gated message', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/baas', {
      timeout: 60000,
      contentSelector: '.baas-page, .unavailable-page',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const baasPage = page.locator('.baas-page');
    const unavailablePage = page.locator('.unavailable-page');
    const hasBaaSContent = (await baasPage.count()) > 0;
    const hasUnavailable = (await unavailablePage.count()) > 0;

    expect(hasBaaSContent || hasUnavailable).toBe(true) /* acceptable states */;
    if (hasUnavailable) {
      await expect(unavailablePage).toContainText(/unavailable|not available|contact/i);
    }
    if (hasBaaSContent) {
      await expect(baasPage.locator('h1')).toContainText(/BaaS|Platform/i);
    }
  });

  test('ML page loads or shows clear gated message', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/ml', {
      timeout: 60000,
      contentSelector: '.ml-page, .unavailable-page',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const mlPage = page.locator('.ml-page');
    const unavailablePage = page.locator('.unavailable-page');
    const hasMLContent = (await mlPage.count()) > 0;
    const hasUnavailable = (await unavailablePage.count()) > 0;

    expect(hasMLContent || hasUnavailable).toBe(true) /* acceptable states */;
    if (hasUnavailable) {
      await expect(unavailablePage).toContainText(/unavailable|not available|contact/i);
    }
    if (hasMLContent) {
      await expect(mlPage.locator('h1')).toContainText(/ML|ODH|Platform/i);
    }
  });

  test('Phase 7 routes are reachable from sidebar when capability present', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, .empty-state, .error-display, h1',
    });
    const sidebar = page.locator('.app-sidebar');
    await expect(sidebar).toBeVisible({ timeout: 10000 });

    // At least one of the Phase 7 nav items may be present (capability-gated)
    const communitiesLink = sidebar.locator('.nav-link').filter({ hasText: /Communities/i });
    const aiLink = sidebar.locator('.nav-link').filter({ hasText: /AI Search/i });
    const devLink = sidebar.locator('.nav-link').filter({ hasText: /Developer/i });
    const baasLink = sidebar.locator('.nav-link').filter({ hasText: /BaaS/i });
    const mlLink = sidebar.locator('.nav-link').filter({ hasText: /ML/i });

    const hasAnyPhase7Link =
      (await communitiesLink.count()) > 0 ||
      (await aiLink.count()) > 0 ||
      (await devLink.count()) > 0 ||
      (await baasLink.count()) > 0 ||
      (await mlLink.count()) > 0;

    // Sidebar must have meaningful navigation (not just 1 link)
    const allNavLinks = sidebar.locator('.nav-link');
    const navCount = await allNavLinks.count();
    expect(navCount, 'Sidebar must have more than 3 nav links after login').toBeGreaterThan(3);

    if (hasAnyPhase7Link) {
      // At least one Phase 7 link is present — verify it navigates without crashing
      const firstPhase7Link =
        (await communitiesLink.count()) > 0
          ? communitiesLink.first()
          : (await aiLink.count()) > 0
            ? aiLink.first()
            : (await devLink.count()) > 0
              ? devLink.first()
              : (await baasLink.count()) > 0
                ? baasLink.first()
                : mlLink.first();

      await firstPhase7Link.click();
      await page.waitForLoadState('domcontentloaded');

      // Must navigate away from /assets — Phase 7 route must be reachable
      const newUrl = page.url();
      expect(newUrl).not.toMatch(/\/assets$/);

      // Page must render some handled state (not a blank screen)
      const hasHandledState =
        (await page
          .locator('.communities-page, .ai-search-page, .developer-portal-page, .baas-page, .ml-page, .unavailable-page, .error-display, h1')
          .count()) > 0;
      expect(hasHandledState, 'Phase 7 route must render a handled UI state').toBe(true) /* acceptable states */;
    }
  });
});
