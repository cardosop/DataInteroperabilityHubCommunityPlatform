/**
 * E2E Journey: JOURNEY-INGESTION-001 — Create and Run Scheduled Ingestion
 *
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md (Scheduled Operations)
 *
 * The REAL job, end-to-end: a MinIO bucket seeded with a CSV is created
 * through the UI with real S3 fields (bucket/prefix/endpoint/credentials),
 * the trigger dispatches the dlt spine, the worker actually discovers the
 * file and ingests it — and the test asserts the run COMPLETED with
 * files_found ≥ 1, files_processed ≥ 1, datasets_created ≥ 1.
 *
 * Replaces the 276.B.105 deferred stub. No mocks — the backend decides.
 */
import { expect, test } from '@playwright/test';
import { gotoWithRetry, type TestUser } from '../../fixtures/auth';
import {
  injectTokensBeforeGotoForUser,
  skipIfRemoteApi,
  waitForAppMainReady,
} from '../../fixtures/helpers';
import { provisionMinioSource } from '../../fixtures/minioSource';
import { API_BASE_URL, fetchWithRetry, login, provisionTenant } from './scheduledJobsHelpers';

interface RunRow {
  id?: string;
  status?: string;
  files_found?: number;
  files_processed?: number;
  files_failed?: number;
  datasets_created?: number;
  error_message?: string | null;
}

test.describe('JOURNEY-INGESTION-001: Create and Run Scheduled Ingestion @critical', () => {
  test.setTimeout(180000);

  test('UI create with real S3 fields → trigger → run COMPLETED with files ingested', async ({
    page,
  }) => {
    skipIfRemoteApi(test, 'Scheduled-ingestion journey requires the local docker stack');
    const tenant = provisionTenant();
    const minio = provisionMinioSource({ bucket: `e2e-ing-${Date.now()}` });

    const token = await login(tenant);
    const user = { email: tenant.email, password: tenant.password } as TestUser;

    // ── Create via the UI with real S3 fields ──────────────────────────
    // Navigate FIRST: injectTokensBeforeGotoForUser writes localStorage
    // via page.evaluate, which throws on about:blank (SecurityError —
    // swallowed by the fixture), silently leaving the storageState user
    // (default tenant) in control of the SPA's X-Tenant-Id.
    await gotoWithRetry(page, '/');
    await injectTokensBeforeGotoForUser(page, user);
    await gotoWithRetry(page, '/scheduled-ingestions/create');
    await waitForAppMainReady(page);

    await page.getByLabel(/name/i).fill(`real-s3-ing-${Date.now()}`);
    await page.getByLabel(/bucket/i).fill(minio.bucket);
    await page.getByLabel(/prefix/i).fill('in/');
    await page.getByLabel(/endpoint url/i).fill(minio.endpoint);
    await page.getByLabel(/access key id/i).fill(minio.accessKeyId);
    await page.getByLabel(/secret access key/i).fill(minio.secretAccessKey);
    await page.getByRole('button', { name: /create/i }).click();

    await page.waitForURL(/\/scheduled-ingestions\/[0-9a-f-]{8,}/, { timeout: 60000 });
    const ingestionId = page.url().split('/').pop()?.split('?')[0] ?? '';
    expect(ingestionId.length).toBeGreaterThanOrEqual(8);
    await waitForAppMainReady(page);
    await expect(page.locator('.scheduled-ingestion-status-badge').first()).toHaveText(
      /ACTIVE/i,
      { timeout: 15000 }
    );

    // ── Trigger through the UI ─────────────────────────────────────────
    await page.getByLabel('Trigger scheduled ingestion').click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 10000 });
    await dialog.getByRole('button', { name: 'Trigger Now' }).click();

    // ── The app does the job: poll the run to COMPLETED with counts ────
    const auth = { Authorization: `Bearer ${token}` };
    await expect
      .poll(
        async () => {
          const resp = await fetchWithRetry(
            `${API_BASE_URL}/scheduled-ingestions/${ingestionId}/runs/`,
            { headers: auth }
          );
          const runs = (await resp.json()) as RunRow[];
          return runs?.[0]?.status ?? 'PENDING';
        },
        { timeout: 120_000, intervals: [1_000, 2_000, 5_000] }
      )
      .toBe('COMPLETED');

    const runsResp = await fetchWithRetry(
      `${API_BASE_URL}/scheduled-ingestions/${ingestionId}/runs/`,
      { headers: auth }
    );
    const run = ((await runsResp.json()) as RunRow[])[0];
    expect(run.error_message, JSON.stringify(run)).toBeFalsy();
    expect(run.files_found, JSON.stringify(run)).toBeGreaterThanOrEqual(1);
    expect(run.files_processed, JSON.stringify(run)).toBeGreaterThanOrEqual(1);
    expect(run.datasets_created, JSON.stringify(run)).toBeGreaterThanOrEqual(1);

    // ── UI reflects the real outcome ───────────────────────────────────
    await page.reload({ waitUntil: 'domcontentloaded' });
    await waitForAppMainReady(page);
    const firstRow = page.locator('.scheduled-ingestion-runs-table tbody tr').first();
    await expect(firstRow).toBeVisible({ timeout: 15000 });
    await expect(firstRow.locator('.run-status-badge')).toHaveText(/COMPLETED/i, {
      timeout: 15000,
    });
  });
});
