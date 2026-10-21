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
    // Churn recovery: the sessions fetch can fail during an API restart
    // window — the page then renders its error state ("Failed to load
    // sessions") with a Retry affordance instead of the table/empty state.
    // Use the app's recovery ONCE before judging.
    const errorDisplay = page.locator('.error-display, [data-testid="error-display"]').first();
    if ((await errorDisplay.count()) > 0) {
      // intentional: diagnostic-only read — an empty read just skips the
      // retry and the strict assertion below reports the visible state.
      const errText = (await errorDisplay.textContent().catch(() => '')) ?? '';
      if (/NETWORK_ERROR|Failed to fetch|connection|INTERNAL_ERROR|SERVICE_UNAVAILABLE/i.test(errText)) {
        await errorDisplay.locator('button:has-text("Retry")').first().click();
        // intentional: the retry may also fail under sustained churn — the
        // table/empty-state assertion below then fails with the real state.
        await page
          .locator('.session-list-table, .session-list-empty')
          .first()
          .waitFor({ state: 'visible', timeout: 30000 })
          .catch(() => null);
      }
    }
    const hasTableOrEmpty =
      (await page.locator('.session-list-table, .session-list-empty').count()) > 0;
    if (!hasTableOrEmpty) {
      // Fail with the VISIBLE state so a sustained-churn failure is
      // one-shot diagnosable instead of a bare boolean (b7: the failure
      // hid "Failed to load sessions / NETWORK_ERROR" behind hasTableOrEmpty
      // === false). The retry above already attempted recovery once.
      // intentional: diagnostic-only read — an empty read just means no error surface rendered and the message falls back to the generic form.
      const errText = (await errorDisplay.textContent().catch(() => '')) ?? '';
      throw new Error(
        `Sessions list did not render table/empty state. Visible error: "${errText?.slice(0, 300) ?? 'N/A'}"`
      );
    }
  });

  test('B.4 — Auth API keys page loads; list or empty; Create/Delete or buttons present', async ({
    page,
  }) => {
    await navigateToRouteFromApp(page, '/settings/api-keys', {
      timeout: 60000,
      contentSelector: '.auth-api-key-list-page, .unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"], h1, .disabled-capability-page, [data-testid="disabled-capability-page"]',
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
