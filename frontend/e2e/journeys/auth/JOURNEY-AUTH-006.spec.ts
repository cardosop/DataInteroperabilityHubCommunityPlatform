/**
 * JOURNEY-AUTH-006 — SSO Login
 *
 * The generic OIDC/SAML SSO button was replaced by the Databricks SSO
 * button (openspec add-databricks-control-plane task 0b.12, JOURNEY-DB-003
 * step 1). ContinueWithDatabricksButton renders whenever /login carries a
 * `?tenant_id=` hint — there is NO capability flag on the render path —
 * and workspace resolution happens on click, so a smoke test needs no real
 * IdP: a click either opens the workspace chooser or surfaces the
 * no-workspaces error. Both are valid outcomes; a crashed page is not.
 *
 * NOTE: the previous incarnation probed `data-testid="sso-login-button"`,
 * which never existed in this codebase's history. That probe always
 * counted 0 and the tests skipped every run — a UI-probe skip that could
 * never catch a render regression. The render assertion below is
 * unconditional, so a regression fails instead of hiding.
 */
import { test, expect } from "@playwright/test";

const LOGIN_URL = "/login";
// Shared default tenant of the test stack (seeded by ensure_e2e_user_roles).
// Any well-formed tenant hint renders the button — the value only matters
// for the click path's workspace resolution.
const TEST_TENANT_ID = "ca06fccd-6092-4fa0-87ec-f5c1ae3c0195";
const SSO_BUTTON_TESTID = "databricks-sso-button";
const SSO_CALLBACK_URL = "/auth/databricks/callback";

test.describe("JOURNEY-AUTH-006 — SSO Login", () => {
  test("Login page renders SSO button when a tenant hint is present", async ({
    page,
  }) => {
    await page.goto(`${LOGIN_URL}?tenant_id=${TEST_TENANT_ID}`);
    await page.waitForLoadState("networkidle");

    // Rendering is gated ONLY on the tenant hint (ContinueWithDatabricksButton
    // returns null without it). Absence here is a regression, not an
    // environment gap — so there is no skip on this assertion.
    const ssoButton = page.getByTestId(SSO_BUTTON_TESTID);
    await expect(ssoButton).toBeVisible({ timeout: 15000 });
    await expect(ssoButton).toHaveText(/Continue with Databricks/);
  });

  test("SSO button click opens the chooser or degrades gracefully", async ({
    page,
  }) => {
    await page.goto(`${LOGIN_URL}?tenant_id=${TEST_TENANT_ID}`);
    await page.waitForLoadState("networkidle");

    const ssoButton = page.getByTestId(SSO_BUTTON_TESTID);
    await expect(ssoButton).toBeVisible({ timeout: 15000 });
    await ssoButton.click();

    // In a real IdP-backed flow this redirects to the workspace chooser /
    // IdP. In the test environment the tenant may have no SSO-eligible
    // workspace — the button then surfaces a no-workspaces error in place.
    // Both are valid smoke outcomes; only a crashed page fails below.
    try {
      await page.waitForURL((url) => !url.pathname.includes("/login"), {
        timeout: 10000,
      });
    } catch {
      // Still on /login — either the chooser/error path or a mocked/absent
      // IdP. Verify the page didn't crash (login form still intact). The
      // click surfaces an in-place alert (e.g. "[NO_TENANT] Request failed
      // with HTTP 400") — a valid degradation — so the assertion targets
      // the email field itself, not a data-testid: login-email-input has
      // never existed on LoginPage (the old probe silently rotted and the
      // assertion failed for a dead locator, 2026-10-03).
      await expect(page.getByRole('textbox', { name: 'Email' })).toBeVisible();
    }
  });

  test("SSO button does not render without a tenant hint", async ({
    page,
  }) => {
    // The current render contract: no ?tenant_id= → the button is not
    // actionable and must not render (workspace resolution needs the hint).
    await page.goto(LOGIN_URL);
    await page.waitForLoadState("networkidle");

    await expect(page.getByTestId(SSO_BUTTON_TESTID)).toHaveCount(0);
  });

  test("SSO callback renders appropriate error state on failure", async ({
    page,
  }) => {
    // Simulate SSO callback with error parameters
    await page.goto(
      `${SSO_CALLBACK_URL}?error=access_denied&error_description=User+cancelled+login`
    );
    await page.waitForLoadState("networkidle");

    // Should show error message, not crash
    const errorElement = page.getByRole("alert");
    // intentional: the error alert is one of two valid terminal states (the
    // other is a redirect to /login); absence is checked by the URL below.
    const hasError = await errorElement.isVisible().catch(() => false);
    // Either error is shown or page redirects to login with error state
    expect(hasError || page.url().includes("login")).toBeTruthy();
  });
});
