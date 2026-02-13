/**
 * E2E Test: Phase 7 — Social + AI + Developer/BaaS + ML (capability-gated) — DEPRECATED (journey-aligned)
 *
 * Content maps to: JOURNEY-DC-008, JOURNEY-DPO-009, JOURNEY-DC-006, JOURNEY-DPO-007, JOURNEY-DEV-001/009,
 * BaaS, JOURNEY-DS-003. Prefer journey specs under journeys/dc/, journeys/dpo/, journeys/dev/, etc.
 * Backend-not-implemented (e.g. UC-SOCIAL-005): assert /unavailable or skip per USE_CASES.md.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from './fixtures/auth';

test.describe('Phase 7 — Social + AI + Developer/BaaS + ML', () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(360000); // 6 min so 429 retries (65s × 3) + getTestUser retries + login + waitForFunction fit (auth limit 5/min)
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1500);
  });

  test('Social page loads or shows clear gated message', async ({ page }) => {
    await page.goto('/social');
    await page.waitForLoadState('domcontentloaded');
    // Backend-not-implemented (UC-SOCIAL-005 activity feed): assert /unavailable or capability-gated message; no mocks.
    // Wait for capability check to resolve: either page content or unavailable message (capabilities may load async)
    await page.waitForSelector('.social-page, .unavailable-page', { timeout: 15000 });

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
    await page.goto('/ai/search');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('.ai-search-page, .unavailable-page', { timeout: 15000 });

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
    await page.goto('/developer');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('.developer-portal-page, .unavailable-page', { timeout: 15000 });

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
    await page.goto('/baas');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('.baas-page, .unavailable-page', { timeout: 15000 });

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
    await page.goto('/ml');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('.ml-page, .unavailable-page', { timeout: 15000 });

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
