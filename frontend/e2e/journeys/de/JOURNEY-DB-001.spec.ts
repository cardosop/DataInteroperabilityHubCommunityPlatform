/**
 * E2E Test: JOURNEY-DB-001 — Register a Databricks Workspace
 *
 * Journey: Register a Databricks Workspace
 * Persona: Data Engineer / Marketplace Platform Admin (TENANT_ADMIN-gated)
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-001.md
 *
 * The guided wizard flow (register → App-connection instructions → test)
 * against the REAL backend: the wizard POSTs a real workspace row through
 * the real validation chain (host-family allowlist + SSRF + residency).
 * Success/Failure sections; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUserOrTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

const MANAGEMENT_SELECTOR = [
  '.warehouse-list',
  '[data-testid="databricks-register-wizard"]',
  '[data-testid="databricks-flag-disabled"]',
  '.error-display, [data-testid="error-display"]',
].join(', ');

test.describe('JOURNEY-DB-001: Register a Databricks Workspace @critical', () => {
  test.setTimeout(240000);

  test.describe('Success', () => {
    test('management page loads and the wizard reaches the credential step', async ({
      page,
    }) => {
      const user = await getTenantAdminUserOrTestUser();
      await loginAndNavigateToRoute(page, user, '/databricks', {
        timeout: 60000,
        contentSelector: MANAGEMENT_SELECTOR,
      });

      // Journey step 1: the management page shows the workspace surface.
      await expect(page.getByRole('heading', { name: /Databricks/i }).first()).toBeVisible({
        timeout: 30000,
      });

      // Open the guided wizard (the CTA is always rendered — the flag is
      // enabled for the e2e tenant by ensure_e2e_user_roles).
      const registerCta = page.getByRole('button', { name: /Register workspace/i });
      await expect(registerCta).toBeVisible({ timeout: 30000 });
      await registerCta.click();

      // Journey step 2: fill the workspace details (real validation on save).
      const wizard = page.locator('[data-testid="databricks-register-wizard"]');
      await expect(wizard).toBeVisible({ timeout: 30000 });

      const unique = Date.now().toString().slice(-10);
      await page.getByLabel(/Workspace name/i).fill(`e2e-journey-${unique}`);
      await page
        .getByLabel(/Workspace host/i)
        .fill('dbc-6710eb95-8fe1.cloud.databricks.com');
      await page.getByLabel(/Cloud/i).selectOption('AWS');
      await page.getByLabel(/Region/i).fill('us-east-1');
      await page.getByRole('button', { name: /Continue/i }).click();

      // Journey step 3: the App-connection instructions surface.
      await expect(page.getByText(/Connect your app/i)).toBeVisible({
        timeout: 30000,
      });
    });
  });

  test.describe('Failure', () => {
    test('a host outside the Databricks family is rejected with the code', async ({
      page,
    }) => {
      const user = await getTenantAdminUserOrTestUser();
      await loginAndNavigateToRoute(page, user, '/databricks', {
        timeout: 60000,
        contentSelector: MANAGEMENT_SELECTOR,
      });

      const registerCta = page.getByRole('button', { name: /Register workspace/i });
      await expect(registerCta).toBeVisible({ timeout: 30000 });
      await registerCta.click();
      const wizard = page.locator('[data-testid="databricks-register-wizard"]');
      await expect(wizard).toBeVisible({ timeout: 30000 });

      await page.getByLabel(/Workspace name/i).fill(`e2e-bad-${Date.now()}`);
      await page.getByLabel(/Workspace host/i).fill('attacker.example.com');
      await page.getByLabel(/Cloud/i).selectOption('AWS');
      await page.getByLabel(/Region/i).fill('us-east-1');
      await page.getByRole('button', { name: /Continue/i }).click();

      // The backend's domain code reaches the UI — operators search runbooks
      // by it (error-envelope parity pinned by the backend suite).
      await expect(
        page.locator('[data-testid="databricks-wizard-error"]')
      ).toContainText('DATABRICKS_HOST_NOT_ALLOWED', { timeout: 30000 });
    });
  });
});
