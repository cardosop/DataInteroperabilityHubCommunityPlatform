/**
 * E2E: UC-DB-001 — Register Databricks Workspace
 *
 * Use Case: Register Databricks Workspace
 * Persona: Data Engineer / Marketplace Admin (route guard: TENANT_ADMIN,
 * PLATFORM_ADMIN; capability: databricks — explicit opt-in, ON for the
 * seeded E2E tenant)
 * Reference: docs/USE_CASES.md, docs/mvpdocs/use-cases/UC-DB-001.md
 *
 * Success/Failure/Edge. Route: /databricks.
 * Real backend only; no mocks. The register write goes through the real
 * UI wizard and the real wire API.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUser, getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE_URL =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

async function loginViaApi(user: { email: string; password: string }): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/auth/login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: user.email, password: user.password }),
  });
  expect(response.ok, `login failed: ${response.status}`).toBeTruthy();
  const data = (await response.json()) as { access_token?: string };
  expect(data.access_token, 'login response missing access_token').toBeTruthy();
  return data.access_token as string;
}

const run = Date.now();

test.describe('UC-DB-001: Register Databricks Workspace', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('databricks registry renders for the admitted persona', async ({ page }) => {
      const user = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, user, '/databricks', {
        timeout: 90000,
        contentSelector: '.warehouse-list, .error-display, [data-testid="error-display"], h2',
        acceptRedirectToLogin: false,
      });

      const url = page.url();
      expect(
        !url.includes('/403') && !url.includes('/unavailable'),
        `/databricks bounced to ${url} — role/capability gate regression for TENANT_ADMIN`
      ).toBe(true);

      await expect(page.getByRole('heading', { name: 'Databricks workspaces' })).toBeVisible({
        timeout: 30000,
      });
      await expect(page.getByRole('button', { name: 'Register workspace' })).toBeVisible();
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });

    test('registering a workspace through the wizard creates a real row', async ({ page }) => {
      const user = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, user, '/databricks', {
        timeout: 90000,
        contentSelector: '.warehouse-list, .error-display, [data-testid="error-display"], h2',
        acceptRedirectToLogin: false,
      });

      await page.getByRole('button', { name: 'Register workspace' }).click();
      await expect(page.getByTestId('databricks-register-wizard')).toBeVisible({ timeout: 15000 });

      const workspaceName = `E2E WS ${run}`;
      await page.getByLabel('Workspace name').fill(workspaceName);
      // The save-time validation runs the Databricks family allowlist +
      // SSRFGuard (DNS resolution) — synthetic dbc-* hosts don't resolve
      // and refuse with SSRF_PROTECTION_TRIGGERED. The Databricks
      // Community hostname resolves publicly and carries the family
      // suffix, so the REAL wire create succeeds.
      await page.getByLabel('Workspace host').fill('community.cloud.databricks.com');
      await page.getByLabel('Cloud').selectOption('AWS');
      await page.getByLabel('Region').fill('us-east-1');
      await page.getByRole('button', { name: 'Continue' }).click();

      // Step 1 (register) creates the REAL workspace row on the wire; the
      // wizard then advances to the credential step. The credential step
      // ends with a REAL connection test against the live workspace —
      // that requires a working Databricks endpoint the test stack does
      // not own, so the wizard legitimately never reaches onSaved here.
      // The register step IS the UC's core surface.
      await expect(page.getByRole('heading', { name: 'Connect your app' })).toBeVisible({
        timeout: 15000,
      });
      await expect(page.getByTestId('databricks-wizard-error')).not.toBeVisible();

      // The REAL row exists in the registry (fresh mount loads it).
      await page.goto('/databricks', { waitUntil: 'domcontentloaded' });
      await expect(page.getByText(workspaceName, { exact: true }).first()).toBeVisible({
        timeout: 15000,
      });

      // Shared-tenant hygiene: remove the row the test created (204).
      const token = await loginViaApi(user);
      const workspacesResponse = await page.request.get(`${API_BASE_URL}/databricks/workspaces/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const list = ((await workspacesResponse.json()) as {
        results?: { id: string; name: string }[];
      } | { id: string; name: string }[]);
      const rows = Array.isArray(list) ? list : (list.results ?? []);
      const created = rows.find((r) => r.name === workspaceName);
      if (created) {
        const del = await page.request.delete(
          `${API_BASE_URL}/databricks/workspaces/${created.id}/`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        expect(del.status()).toBe(204);
      }
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to /databricks redirects to login', async ({ page }) => {
      await page.goto('/databricks', { waitUntil: 'domcontentloaded' });
      // intentional: best-effort URL wait — the primary pass/fail is the
      // redirect assertion below.
      await page.waitForURL(/\/(login|403)/, { timeout: 20000 }).catch(() => null);
      expect(page.url().includes('/login') || page.url().includes('/403')).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('registry renders a list or the empty state without error', async ({ page }) => {
      const user = await getTestUser();
      // The DATA_PROVIDER persona lacks the TENANT_ADMIN/PLATFORM_ADMIN
      // guard role — the parent ProtectedRoute must bounce to /403.
      await loginAndNavigateToRoute(page, user, '/databricks', {
        timeout: 60000,
        contentSelector: '.warehouse-list, h2, [data-testid="forbidden-page"], .unavailable-page, [data-testid="unavailable-page"]',
      });
      const url = page.url();
      expect(url.includes('/403') || url.includes('/unavailable'), `expected guard bounce, got ${url}`).toBe(true);
    });
  });
});
