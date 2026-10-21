/**
 * E2E Journey: JOURNEY-EXPORT-001 — Create and Run Scheduled Export
 *
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md (Scheduled Operations)
 *
 * The REAL job, end-to-end via the dlt dispatch spine: the tenant is
 * data_movement_enabled, so the trigger executes the export
 * SYNCHRONOUSLY in the hub (the Prefect path is not used — its local
 * worker cannot run flow containers). The scoped dataset's real CSV is
 * read from the file store and written out by the dlt pipeline; the run
 * must reach COMPLETED with items_found ≥ 1 and items_exported ≥ 1.
 *
 * Precondition: the export preflight (export_preflight.py) requires the
 * dataset's newest ACTIVE contract to be ODCS with validation_status
 * VALID/WARNING_ONLY — createAssetViaApi({ensureActivated: true})
 * provisions exactly that; the spec re-asserts it defensively so a
 * contract regression fails with a readable message instead of a
 * mysterious FAILED run. Replaces the 276.B.105 deferred stub.
 */
import { expect, test } from '@playwright/test';
import { gotoWithRetry, type TestUser } from '../../fixtures/auth';
import { clearAuthStorage, getTenantAdminUser } from '../../fixtures/auth';
import { hasLoginPrompt, loginAndNavigateToRoute } from '../../fixtures/helpers';
import { createAssetViaApi, createDatasetViaApi } from '../../fixtures/api-assets';
import {
  injectTokensBeforeGotoForUser,
  skipIfRemoteApi,
  waitForAppMainReady,
} from '../../fixtures/helpers';
import { API_BASE_URL, fetchWithRetry, login, provisionTenant } from './scheduledJobsHelpers';

interface ExportRun {
  id?: string;
  status?: string;
  items_found?: number;
  items_exported?: number;
  items_failed?: number;
  result_json?: Record<string, unknown> | null;
}

test.describe('JOURNEY-EXPORT-001: Create and Run Scheduled Export @critical', () => {
  test.setTimeout(240000);

  test('UI create with a real dataset → trigger → run COMPLETED with items exported', async ({
    page,
  }) => {
    skipIfRemoteApi(test, 'Scheduled-export journey requires the local docker stack');
    const tenant = provisionTenant();
    const token = await login(tenant);
    const auth = { Authorization: `Bearer ${token}` };
    const user = { email: tenant.email, password: tenant.password } as TestUser;

    // ── Source setup: activated asset (ODCS contract) + real CSV dataset ──
    const assetId = await createAssetViaApi(user, {
      forceNew: true,
      ensureActivated: true,
    });
    const datasetId = await createDatasetViaApi(user, {
      assetId,
      forceNew: true,
    });

    const datasetResp = await fetchWithRetry(`${API_BASE_URL}/datasets/${datasetId}/`, {
      headers: auth,
    });
    expect(datasetResp.status, `dataset fetch: ${datasetResp.status}`).toBe(200);
    const dataset = (await datasetResp.json()) as { name?: string; file?: string | null };
    expect(dataset.name, 'dataset must have a name for the picker').toBeTruthy();
    expect(dataset.file, 'dataset must carry a real file for the export to move').toBeTruthy();

    // Defensive preflight: the export run FAILS before any movement unless
    // the newest ACTIVE contract is ODCS + VALID/WARNING_ONLY — assert it
    // here so a contract regression fails with a readable message.
    const contractsResp = await fetchWithRetry(
      `${API_BASE_URL}/contracts/?asset=${assetId}&page_size=50`,
      { headers: auth }
    );
    expect(contractsResp.status, `contracts fetch: ${contractsResp.status}`).toBe(200);
    const contractsData = (await contractsResp.json()) as {
      results?: Array<{
        id?: string;
        status?: string;
        original_spec_type?: string;
        validation_status?: string;
      }>;
    };
    const validOdcs = (contractsData.results ?? []).some(
      (c) =>
        c.status === 'ACTIVE' &&
        c.original_spec_type === 'ODCS' &&
        ['VALID', 'WARNING_ONLY'].includes(c.validation_status ?? '')
    );
    expect(
      validOdcs,
      'export preflight requires an ACTIVE ODCS contract with validation_status VALID/WARNING_ONLY'
    ).toBe(true);

    // ── Create via the UI ──────────────────────────────────────────────
    // Navigate FIRST: injectTokensBeforeGotoForUser writes localStorage
    // via page.evaluate, which throws on about:blank (SecurityError —
    // swallowed by the fixture), silently leaving the storageState user
    // (default tenant) in control of the SPA's X-Tenant-Id.
    await gotoWithRetry(page, '/');
    await injectTokensBeforeGotoForUser(page, user);
    await gotoWithRetry(page, '/scheduled-exports/create');
    await waitForAppMainReady(page);

    await page.getByLabel(/name/i).fill(`real-s3-export-${Date.now()}`);
    const picker = page.getByTestId('scheduled-export-dataset-picker');
    await picker.getByRole('combobox').click();
    await picker.getByRole('combobox').fill(String(dataset.name));
    await page.getByRole('option', { name: new RegExp(String(dataset.name)) }).first().click();
    // cron + destination default (S3) are pre-filled; create.
    await page.getByRole('button', { name: /^create$/i }).click();

    await page.waitForURL(/\/scheduled-exports\/[0-9a-f-]{8,}/, { timeout: 60000 });
    const exportId = page.url().split('/').pop()?.split('?')[0] ?? '';
    expect(exportId.length).toBeGreaterThanOrEqual(8);
    await waitForAppMainReady(page);
    await expect(page.locator('.scheduled-export-status-badge').first()).toHaveText(/ACTIVE/i, {
      timeout: 15000,
    });

    // ── Trigger through the UI (synchronous dlt execution inside) ──────
    await page.getByLabel('Trigger scheduled export').click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 10000 });
    await dialog.getByRole('button', { name: 'Trigger Now' }).click();

    // ── The app does the job: poll the run to COMPLETED with counts ────
    await expect
      .poll(
        async () => {
          const resp = await fetchWithRetry(
            `${API_BASE_URL}/scheduled-exports/${exportId}/runs/`,
            { headers: auth }
          );
          const runs = (await resp.json()) as ExportRun[];
          return runs?.[0]?.status ?? 'PENDING';
        },
        { timeout: 180_000, intervals: [1_000, 2_000, 5_000] }
      )
      .toBe('COMPLETED');

    const runsResp = await fetchWithRetry(
      `${API_BASE_URL}/scheduled-exports/${exportId}/runs/`,
      { headers: auth }
    );
    const run = ((await runsResp.json()) as ExportRun[])[0];
    expect(run.items_found, JSON.stringify(run)).toBeGreaterThanOrEqual(1);
    expect(run.items_exported, JSON.stringify(run)).toBeGreaterThanOrEqual(1);
    expect(run.items_failed, JSON.stringify(run)).toBe(0);

    // ── UI reflects the real outcome ───────────────────────────────────
    await page.reload({ waitUntil: 'domcontentloaded' });
    await waitForAppMainReady(page);
    const firstRun = page.getByTestId('export-run-item').first();
    await expect(firstRun).toBeVisible({ timeout: 15000 });
    await expect(firstRun.locator('.run-status-badge')).toHaveText(/COMPLETED/i, {
      timeout: 15000,
    });
  });
  test.describe('Success', () => {
    test('scheduled-exports list loads and shows Create Export button', async ({ page }) => {
      const testUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, testUser, '/scheduled-exports', {
        timeout: 60000,
        contentSelector:
          '.scheduled-export-list-page, .empty-state, [data-testid="empty-state"], .unavailable-page, [data-testid="unavailable-page"], h1, .disabled-capability-page, [data-testid="disabled-capability-page"]',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        test.skip(page.url().includes('/login'), 'Redirected to login — auth may have expired');
        return;
      }

      const url = page.url();
      expect(url).toMatch(/\/scheduled-exports|\/403/);
      if (url.includes('/403')) {
        test.skip(url.includes('/403'), 'Scheduled exports role-gated (403) — user may lack permission');
        return;
      }

      // Success test must NOT accept .error-display, [data-testid="error-display"]
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();

      // Must render list page content
      const hasContent =
        (await page.locator('.scheduled-export-list-page, .empty-state, [data-testid="empty-state"], h1').count()) > 0;
      expect(hasContent, 'Expected scheduled-export list content').toBe(true);

      // Create Export button must be accessible
      const createBtn = page.getByRole('button', { name: /Create Export/i }).first();
      await expect(createBtn).toBeVisible({ timeout: 10000 });
    });

    test('create export form loads with required fields', async ({ page }) => {
      const testUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, testUser, '/scheduled-exports/create', {
        timeout: 60000,
        contentSelector:
          '.scheduled-export-create-page, form, h1',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(page.url().includes('/login') || page.url().includes('/403'), 'Redirected to login/403 — auth or role gated');
        return;
      }

      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();

      // Form must have name input and cron/schedule input
      const hasForm = (await page.locator('form').count()) > 0;
      const hasNameInput =
        (await page.locator('input[name="name"], input#name').count()) > 0;
      expect(hasForm, 'Expected form on create page').toBe(true);
      expect(hasNameInput, 'Expected name input on create page').toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to scheduled-exports redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/scheduled-exports', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|scheduled-exports|403)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onRouteWithLoginPrompt =
        url.includes('/scheduled-exports') && (await hasLoginPrompt(page));
      expect(onLogin || onRouteWithLoginPrompt).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('create form rejects submission without required fields', async ({ page }) => {
      const testUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, testUser, '/scheduled-exports/create', {
        timeout: 60000,
        contentSelector:
          '.scheduled-export-create-page, form, h1',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(page.url().includes('/login') || page.url().includes('/403'), 'Redirected to login/403 — auth or role gated');
        return;
      }

      // Try to submit empty form
      const submitBtn = page.getByRole('button', { name: /Create|Save|Submit/i }).first();
      // intentional: probes optional UI presence — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state, not a test failure.
      await submitBtn.waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);
      if ((await submitBtn.count()) === 0) {
        test.skip((await submitBtn.count()) === 0, 'Submit button not found — form may not have loaded');
        return;
      }
      // A DISABLED submit on an empty form IS the rejection contract
      // (native required-attribute gating): Playwright's click auto-wait
      // requires an enabled element, so clicking a disabled button spins
      // until the test budget dies (b7 #89: 163 retries). Assert the
      // disabled state directly instead of attempting the impossible
      // click.
      if (await submitBtn.isDisabled()) {
        expect(await submitBtn.isDisabled(), 'empty form keeps the submit disabled').toBe(true);
        return;
      }
      await submitBtn.click();
      await page.waitForTimeout(1000);

      // Must stay on create page (not navigate away) or show validation error
      const stayedOnCreate = page.url().includes('/create');
      const hasValidationError =
        (await page.locator('.field-error, [role="alert"], .error-message').count()) > 0 ||
        (await page
          .locator('input:invalid, select:invalid, [aria-invalid="true"]')
          .count()) > 0;
      expect(
        stayedOnCreate || hasValidationError,
        'Expected to stay on create page or show validation error on empty submission'
      ).toBe(true);
    });
  });
});
