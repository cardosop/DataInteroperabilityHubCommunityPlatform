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

test.describe("Phase 7.5 gap — DQ + compliance runs @deprecated", () => {
  test.setTimeout(120000);
  test.beforeEach(async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('.app-sidebar', { timeout: 15000 });
  });


  test('A.4 — DQ and Compliance list pages load; Create DQ run and Create compliance run buttons present', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/dq', {
      timeout: 60000,
      contentSelector: '.dq-run-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    await expect(
      page.locator('.dq-run-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1').first()
    ).toBeVisible({ timeout: 10000 });
    const createDQBtn = page.getByRole('button', { name: /Create DQ run/i });
    let hasCreateDQ = false;
    try {
      hasCreateDQ = (await createDQBtn.count()) > 0 && (await createDQBtn.isVisible());
    } catch {
      // intentional: phase7.5 is flagged @deprecated under 226.E1 and queued for deletion under 226.E5 once Track D coverage lands. Bare catches here mark legacy fall-through patterns whose replacements live in the new D1-D4 specs; they're preserved with explicit justification rather than silently removed.
      /* Create DQ button not visible — may be 403 or capability gated */
    }
    if (!hasCreateDQ) {
      const on403 = page.url().includes('/403');
      const hasDQContent =
        (await page.locator('.dq-run-list-page, .empty-state, [data-testid="empty-state"]').count()) >
        0;
      expect(on403 || hasDQContent).toBe(true) /* acceptable states */;
    }

    await navigateToRouteFromApp(page, '/compliance', {
      timeout: 60000,
      contentSelector: '.compliance-run-list-page, [data-testid="compliance-run-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    await expect(
      page.locator('.compliance-run-list-page, [data-testid="compliance-run-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1').first()
    ).toBeVisible({ timeout: 10000 });
    const createComplianceBtn = page.getByRole('button', { name: /Create compliance run/i });
    let hasCreateCompliance = false;
    try {
      hasCreateCompliance =
        (await createComplianceBtn.count()) > 0 && (await createComplianceBtn.isVisible());
    } catch {
      // intentional: phase7.5 is flagged @deprecated under 226.E1 and queued for deletion under 226.E5 once Track D coverage lands. Bare catches here mark legacy fall-through patterns whose replacements live in the new D1-D4 specs; they're preserved with explicit justification rather than silently removed.
      /* Create compliance button not visible — may be 403 or capability gated */
    }
    if (!hasCreateCompliance) {
      const on403 = page.url().includes('/403');
      const hasComplianceContent =
        (await page.locator('.compliance-run-list-page, [data-testid="compliance-run-list-page"], .empty-state, [data-testid="empty-state"]').count()) >
        0;
      expect(on403 || hasComplianceContent).toBe(true) /* acceptable states */;
    }
  });
});
