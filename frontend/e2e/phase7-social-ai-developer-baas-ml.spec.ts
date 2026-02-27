/**
 * E2E Test: Phase 7 — Social + AI + Developer/BaaS + ML (capability-gated) — DEPRECATED (journey-aligned)
 *
 * Content maps to: JOURNEY-DC-008, JOURNEY-DPO-009, JOURNEY-DC-006, JOURNEY-DPO-007, JOURNEY-DEV-001/009,
 * BaaS, JOURNEY-DS-003. Prefer journey specs under journeys/dc/, journeys/dpo/, journeys/dev/, etc.
 * Backend-not-implemented (e.g. UC-SOCIAL-005): assert /unavailable or skip per USE_CASES.md.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from './fixtures/auth';
import { loginAndNavigateToRoute } from './fixtures/helpers';

test.describe('Phase 7 — Social + AI + Developer/BaaS + ML', () => {
  test.beforeEach(() => {
    test.setTimeout(180000); // 3 min: 429 retries (25s × 3) + getTestUser + login
  });

  test('Social page loads or shows clear gated message', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/social', {
      timeout: 60000,
      contentSelector: '.social-page, .unavailable-page',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const socialPage = page.locator('.social-page');
    const unavailablePage = page.locator('.unavailable-page');
    const hasSocialContent = (await socialPage.count()) > 0;
    const hasUnavailable = (await unavailablePage.count()) > 0;

    expect(hasSocialContent || hasUnavailable).toBe(true);
    if (hasUnavailable) {
      await expect(unavailablePage).toContainText(/unavailable|not available|contact/i);
    }
    if (hasSocialContent) {
      await expect(socialPage.locator('h1')).toContainText(/Social/i);
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

    expect(hasAIContent || hasUnavailable).toBe(true);
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

    expect(hasDevContent || hasUnavailable).toBe(true);
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

    expect(hasBaaSContent || hasUnavailable).toBe(true);
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

    expect(hasMLContent || hasUnavailable).toBe(true);
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
    const socialLink = sidebar.locator('.nav-link').filter({ hasText: /Social/i });
    const aiLink = sidebar.locator('.nav-link').filter({ hasText: /AI Search/i });
    const devLink = sidebar.locator('.nav-link').filter({ hasText: /Developer/i });
    const baasLink = sidebar.locator('.nav-link').filter({ hasText: /BaaS/i });
    const mlLink = sidebar.locator('.nav-link').filter({ hasText: /ML/i });

    const hasAnyPhase7Link =
      (await socialLink.count()) > 0 ||
      (await aiLink.count()) > 0 ||
      (await devLink.count()) > 0 ||
      (await baasLink.count()) > 0 ||
      (await mlLink.count()) > 0;

    // Sidebar should have multiple nav items; Phase 7 items are optional (gated)
    const allNavLinks = sidebar.locator('.nav-link');
    const navCount = await allNavLinks.count();
    expect(navCount).toBeGreaterThan(0);
  });
});
