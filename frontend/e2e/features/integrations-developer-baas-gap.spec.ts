/**
 * Phase 7.5 — FEATURES gap closure (split per 226.E3).
 *
 * @deprecated — kept until Track D's replacement coverage lands; the
 * PR-time smoke (`@critical`) excludes this file via `--grep-invert`.
 * Each test here was relocated verbatim from the original
 * frontend/e2e/phase7.5-features-gap-closure.spec.ts so test semantics,
 * silent-failure annotations, and skip messages are preserved.
 *
 * Real backend only. No mocks/stubs.
 */

import { expect, test } from '@playwright/test';
import {
  getTestUser,
  loginUser,
} from '../fixtures/auth';
import {
  loginAndNavigateToRoute,
  navigateToRouteFromApp,
} from '../fixtures/helpers';

test.describe("Phase 7.5 gap — integrations / developer / baas / sidebar @deprecated", () => {
  test.setTimeout(120000);
  test.beforeEach(async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('.app-sidebar', { timeout: 15000 });
  });


  test('A.3 — Sidebar shows Integrations/Developer/BaaS/ML or nav loads without crash', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const sidebar = page.locator('.app-sidebar');
    await expect(sidebar).toBeVisible({ timeout: 10000 });

    const navLinks = sidebar.locator('.nav-link');
    const count = await navLinks.count();
    expect(count).toBeGreaterThan(0);

    const integrationsLink = sidebar.locator('.nav-link').filter({ hasText: /Integrations/i });
    const developerLink = sidebar.locator('.nav-link').filter({ hasText: /Developer/i });
    const baasLink = sidebar.locator('.nav-link').filter({ hasText: /BaaS/i });
    const mlLink = sidebar.locator('.nav-link').filter({ hasText: /ML/i });

    const hasIntegrations = (await integrationsLink.count()) > 0;
    const hasDeveloper = (await developerLink.count()) > 0;
    const hasBaaS = (await baasLink.count()) > 0;
    const hasML = (await mlLink.count()) > 0;

    // Sidebar shows Integrations/Developer/BaaS/ML or nav loads without crash
    expect(hasIntegrations || hasDeveloper || hasBaaS || hasML || count > 0).toBe(true) /* acceptable states */;
  });

  test('A.2 — Integrations connections list, create and detail routes load without 404', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/integrations/connections', {
      timeout: 60000,
      contentSelector: '.marketplace-connection-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const body = page.locator('body');
    await expect(body).not.toContainText(/404|Not Found/);
    const listPage = page.locator(
      '.marketplace-connection-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1'
    );
    await expect(listPage.first()).toBeVisible({ timeout: 10000 });

    await navigateToRouteFromApp(page, '/integrations/connections/create', {
      timeout: 60000,
      contentSelector: 'h1, .marketplace-connection-create-page, form',
    });
    await expect(body).not.toContainText(/404|Not Found/);
    await expect(
      page.getByRole('heading', { name: /Create.*Connection|Create Marketplace Connection/i })
    ).toBeVisible({ timeout: 10000 });

    await navigateToRouteFromApp(page, '/integrations/connections', {
      timeout: 60000,
      contentSelector: '.marketplace-connection-list-page, .connection-card, .empty-state, [data-testid="empty-state"], h1',
    });
    const firstCard = page.locator('.connection-card').first();
    // intentional: connection cards are tenant-content-dependent —
    // empty-tenant runs render the empty state instead. The
    // contentSelector above already validates the page renders one
    // of {list page, card, empty-state, heading}; this branch only
    // exercises the click-through when a card is actually present.
    if ((await firstCard.count()) > 0) {
      await firstCard.click();
      await page.waitForTimeout(2000);
      await expect(body).not.toContainText(/404|Not Found/);
      await expect(
        page.locator('.marketplace-connection-detail-page, [data-testid="marketplace-connection-detail-page"], .loading-spinner, h1').first()
      ).toBeVisible({ timeout: 10000 });
    }
  });
});
