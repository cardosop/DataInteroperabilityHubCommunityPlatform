/**
 * E2E Test: JOURNEY-DB-003 — Sign in with Databricks
 *
 * Persona: Any (visitor)
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-003.md
 *
 * Real backend: the login page renders the "Continue with Databricks"
 * button only with a tenant hint, and clicking it exercises the REAL
 * workspaces endpoint. The default e2e tenant has the SSO flag OFF
 * (0b.10 default-off), so the pinned path is the gating contract — the
 * 403 DATABRICKS_SSO_DISABLED code must reach the UI.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { getMeViaApi } from '../../fixtures/api-users';

test.describe('JOURNEY-DB-003: Sign in with Databricks @critical', () => {
  test.setTimeout(120000);

  test.describe('Failure (gated)', () => {
    test('button click surfaces DATABRICKS_SSO_DISABLED when the flag is off', async ({
      page,
    }) => {
      // Tenant hint: the REAL e2e default tenant — SSO flag off by
      // default. A hardcoded UUID (…000001) does not exist in the stack:
      // the anonymous workspaces endpoint then 400s NO_TENANT before the
      // SSO gate ever runs and the UI shows a generic 400 instead of the
      // typed DATABRICKS_SSO_DISABLED code.
      const user = await getTestUser();
      const me = await getMeViaApi(user);
      await page.goto(`/login?tenant_id=${me.tenant_id}`);
      const button = page.getByTestId('databricks-sso-button');
      await expect(button).toBeVisible({ timeout: 30000 });
      await button.click();
      await expect(page.getByText(/DATABRICKS_SSO_DISABLED/)).toBeVisible({
        timeout: 30000,
      });
    });
  });

  test.describe('Visibility', () => {
    test('button hidden without a tenant hint', async ({ page }) => {
      await page.goto('/login');
      await expect(
        page.getByTestId('databricks-sso-button')
      ).not.toBeVisible({ timeout: 30000 });
    });
  });
});
