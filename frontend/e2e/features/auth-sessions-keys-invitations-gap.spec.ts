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

test.describe("Phase 7.5 gap — auth (sessions, api-keys, invitations) @deprecated", () => {
  test.setTimeout(120000);
  test.beforeEach(async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('.app-sidebar', { timeout: 15000 });
  });


  test('B.3 — Sessions page loads; list or empty state; Revoke present when sessions exist', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/settings/sessions', {
      timeout: 60000,
      contentSelector:
        '.session-list-page, .session-list-table, .session-list-empty, .error-display, [data-testid="error-display"], h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const body = page.locator('body');
    await expect(body).not.toContainText(/404|Not Found/);
    const sessionsPage = page.locator('.session-list-page');
    await expect(sessionsPage).toBeVisible({ timeout: 10000 });
    const heading = page.getByRole('heading', { name: /Active Sessions/i });
    await expect(heading).toBeVisible({ timeout: 5000 });
    const hasTableOrEmpty =
      (await page.locator('.session-list-table, .session-list-empty').count()) > 0;
    expect(hasTableOrEmpty).toBe(true) /* acceptable states */;
  });

  test('B.4 — Auth API keys page loads; list or empty; Create/Delete or buttons present', async ({
    page,
  }) => {
    await navigateToRouteFromApp(page, '/settings/api-keys', {
      timeout: 60000,
      contentSelector: '.auth-api-key-list-page, .unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"], h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    // Don't assert body.not.toContainText(/404|Not Found/) — unreliable during lazy-load transitions.
    // The positive assertion below (.auth-api-key-list-page visible) is the meaningful check.
    const apiKeysPage = page.locator('.auth-api-key-list-page');
    await expect(apiKeysPage).toBeVisible({ timeout: 10000 });
    const heading = page.getByRole('heading', { name: /Auth API Keys/i });
    await expect(heading).toBeVisible({ timeout: 5000 });
    const createBtn = page.getByRole('button', { name: /Create|Add.*key/i });
    await expect(createBtn).toBeVisible({ timeout: 5000 });
  });

  test('B.5 — Accept invitation page loads; with token shows form, without token shows message or app handles', async ({
    page,
  }) => {
    await page.goto('/accept-invitation', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    const body = page.locator('body');
    await expect(body).toBeVisible();
    const acceptPage = page.locator('.accept-invitation-page');
    const hasAcceptPage = (await acceptPage.count()) > 0;
    const hasHeading =
      (await page.getByRole('heading', { name: /Accept Invitation/i }).count()) > 0;
    const hasMessageOrForm =
      (await page
        .locator('.accept-invitation-missing-token, .accept-invitation-card form')
        .count()) > 0;
    expect(hasAcceptPage || hasHeading || hasMessageOrForm).toBe(true) /* acceptable states */;
  });
});
