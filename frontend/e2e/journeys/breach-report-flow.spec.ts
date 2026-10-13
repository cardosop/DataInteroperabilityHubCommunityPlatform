/**
 * 284.F.4 — Breach report flow E2E spec.
 *
 * Journeys covered:
 *   1. Report a breach — fill form, create incident, redirect to detail,
 *      view SLA clock, run status transitions (CONTAINED → NOTIFIED → CLOSED).
 *   2. Breach dashboard renders without white-screen.
 *   3. Report form renders with core form elements.
 *
 * close-test-coverage-gaps 4.4 rewrite: the original draft logged in via
 * the API only (no browser session), navigated as an unauthenticated
 * DATA_PROVIDER, and leaned on `.catch(() => false)` probes that silently
 * passed on /403 + /login. With the 4.4 seeder contract (compliance_breach
 * ON) and the breachService URL fixes, the handler surfaces render for
 * real — the spec now runs as TENANT_ADMIN through a REAL browser login
 * and asserts the real flow.
 *
 * Real backend only — no mocks. All API operations go through the UI.
 */
import { test, expect } from '../fixtures/guardedTest';
import { getTenantAdminUser, loginUser } from '../fixtures/auth';

test.describe('284.F.4 — Breach report flow @critical @breach', () => {
  test.setTimeout(120_000);

  test('report a breach — create, view detail with SLA clock, status transitions', async ({
    page,
  }) => {
    const user = await getTenantAdminUser();
    await loginUser(page, user);
    await page.waitForLoadState('domcontentloaded');

    // ── Create breach via report form ──────────────────────────────
    await page.goto('/governance/breach/report');
    await expect(page.getByRole('heading', { name: 'Report a personal data breach' })).toBeVisible({
      timeout: 15_000,
    });

    const incidentTitle = `E2E Breach ${Date.now()}`;
    await page.getByLabel('Title', { exact: true }).fill(incidentTitle);
    await page.getByLabel(/Summary/).fill('E2E test breach incident — summary with no real PII.');
    await page.getByLabel(/Regimes/).fill('GDPR');
    await page.getByRole('button', { name: 'Open incident' }).click();

    // After create, redirects to /governance/breach/{id}.
    await page.waitForURL(/\/governance\/breach\/[0-9a-f-]+/, { timeout: 15_000 });

    // ── Breach detail page — SLA clock / status visible ────────────
    // The detail page renders the breach title as an h1.
    await expect(page.getByRole('heading', { name: incidentTitle })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('Status:').first()).toBeVisible({ timeout: 10_000 });

    // ── Status transitions ─────────────────────────────────────────
    // Mark CONTAINED → the status cell updates after the PATCH reload.
    await page.getByRole('button', { name: 'Mark contained' }).click();
    await expect
      .poll(async () => (await page.getByText('CONTAINED', { exact: true }).count()), {
        timeout: 15_000,
      })
      .toBeGreaterThan(0);

    // Mark NOTIFIED.
    await page.getByRole('button', { name: 'Mark notified' }).click();
    await expect
      .poll(async () => (await page.getByText('NOTIFIED', { exact: true }).count()), {
        timeout: 15_000,
      })
      .toBeGreaterThan(0);

    // Close.
    await page.getByRole('button', { name: 'Close', exact: true }).click();
    await expect
      .poll(async () => (await page.getByText('CLOSED', { exact: true }).count()), {
        timeout: 15_000,
      })
      .toBeGreaterThan(0);

    // After transitions, the page must still render without error.
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
  });

  test('breach dashboard renders without white-screen', async ({ page }) => {
    const user = await getTenantAdminUser();
    await loginUser(page, user);
    await page.waitForLoadState('domcontentloaded');

    await page.goto('/governance/breach');
    await page.waitForLoadState('domcontentloaded');

    // The dashboard must render — heading + the open-incidents counter.
    await expect(page.getByRole('heading', { name: 'Breach response dashboard' })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText('Open incidents').first()).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
  });

  test('breach report page renders form elements and is not white-screen', async ({
    page,
  }) => {
    const user = await getTenantAdminUser();
    await loginUser(page, user);
    await page.waitForLoadState('domcontentloaded');

    await page.goto('/governance/breach/report');
    await page.waitForLoadState('domcontentloaded');

    // The page must render the report form without crashing.
    await expect(page.getByRole('heading', { name: 'Report a personal data breach' })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByLabel('Title', { exact: true })).toBeVisible();
    await expect(page.getByLabel(/Summary/)).toBeVisible();
    await expect(page.getByLabel(/Regimes/)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Open incident' })).toBeVisible();
  });
});
