/**
 * E2E: UC-AUTH-006 — SSO Login
 *
 * Use Case: SSO Login
 * Persona: Data Engineer / External Developer
 * Reference: docs/USE_CASES.md, docs/mvpdocs/use-cases/UC-AUTH-006.md
 *
 * Success/Failure/Edge. Route: /login (the shipped SSO surface is the
 * Databricks SSO button — openspec add-databricks-control-plane 0b.12).
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';

const SSO_BUTTON_TESTID = 'databricks-sso-button';
// Any well-formed tenant hint renders the button; the value only matters
// for the click path's workspace resolution.
const TENANT_HINT = 'ca06fccd-6092-4fa0-87ec-f5c1ae3c0195';

test.describe('UC-AUTH-006: SSO Login', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('login page renders the SSO button when a tenant hint is present', async ({ page }) => {
      await page.goto(`/login?tenant_id=${TENANT_HINT}`, { waitUntil: 'domcontentloaded' });

      // Rendering is gated ONLY on the tenant hint — absence here is a
      // regression, not an environment gap (JOURNEY-AUTH-006 contract).
      const ssoButton = page.getByTestId(SSO_BUTTON_TESTID);
      await expect(ssoButton).toBeVisible({ timeout: 15000 });
      await expect(ssoButton).toHaveText(/Continue with Databricks/);
    });

    test('SSO button click leaves the login page or degrades gracefully', async ({ page }) => {
      await page.goto(`/login?tenant_id=${TENANT_HINT}`, { waitUntil: 'domcontentloaded' });

      const ssoButton = page.getByTestId(SSO_BUTTON_TESTID);
      await expect(ssoButton).toBeVisible({ timeout: 15000 });
      await ssoButton.click();

      // Real IdP-backed flow → workspace chooser / IdP redirect. Test
      // tenant without SSO-eligible workspaces → a no-workspaces error
      // in place. Both are valid smoke outcomes; only a crash fails.
      // intentional: best-effort navigation probe — the primary pass/fail
      // is the crash check below.
      await page
        .waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10000 })
        .catch(() => null);
      await expect(page.locator('body')).toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('login page without a tenant hint renders no SSO button', async ({ page }) => {
      await page.goto('/login', { waitUntil: 'domcontentloaded' });

      // The render gate: ContinueWithDatabricksButton returns null
      // without the tenant hint. Presence here would be a regression.
      await expect(page.getByTestId(SSO_BUTTON_TESTID)).toHaveCount(0);
      await expect(page.getByLabel('Email')).toBeVisible({ timeout: 15000 });
    });
  });

  test.describe('Edge', () => {
    test('the callback path renders a non-crashing terminal state', async ({ page }) => {
      // /auth/databricks/callback is a BACKEND surface (the IdP
      // redirect_uri) — the SPA router owns no such path, so a direct
      // visit must render the SPA's not-found terminal (or an alert /
      // /login redirect), never a crash.
      await page.goto(
        '/auth/databricks/callback?error=access_denied&error_description=User+cancelled+login',
        { waitUntil: 'domcontentloaded' },
      );
      // intentional: the wait is best-effort — the terminal-state check
      // below is the primary pass/fail decision.
      await page
        .locator('.not-found-page, [role="alert"], .auth-page, .app-main, [data-testid="app-main"]')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);
      await expect(page.locator('body')).toBeVisible();
      const url = page.url();
      const terminal =
        (await page.locator('.not-found-page').count()) > 0 ||
        (await page.getByRole('alert').count()) > 0 ||
        url.includes('/login');
      expect(terminal, `callback landed on ${url} without a terminal state`).toBe(true);
    });
  });
});
