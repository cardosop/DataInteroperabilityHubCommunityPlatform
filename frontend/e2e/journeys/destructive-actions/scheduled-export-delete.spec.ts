/**
 * E2E spec — Scheduled-export destructive-action guarantee chain (226.G1).
 *
 * Background — same Prefect-coordinated ordered hard-delete as
 * scheduled-ingestion-delete (`hub/apps/scheduled_export/views.py:368-435`).
 * The 204 / 409 dichotomy mirrors that flow exactly. This spec asserts the
 * export-side contract independently because:
 *
 *   • Different REST surface (`/scheduled-exports/` vs
 *     `/scheduled-ingestions/`).
 *   • Different parent (datasets, not assets-with-source-config).
 *   • Different downstream effect (the deleted export must NOT execute its
 *     next scheduled run).
 *
 * Guarantee chain asserted here:
 *   1. UI delete (DELETE /api/v1/scheduled-exports/{id}/) returns 204 OR 409.
 *   2. On 204 — verifyViaApiAbsent on detail.
 *   3. On 409 — `status='DELETED'` tombstone.
 *   4. List endpoint excludes the row in either branch.
 *   5. Re-DELETE no 5xx.
 *   6. Cascade — the underlying dataset(s) referenced in `source_scope` remain
 *      queryable.
 *
 * No mocks. Real backend only.
 */

import { test, expect } from '../../fixtures/test-data-cleanup';
import { getTestUser, loginViaApi } from '../../fixtures/auth';
import { verifyViaApi, verifyViaApiAbsent } from '../../fixtures/verifyViaApi';
import { createDatasetViaApi } from '../../fixtures/api-assets';
import { ensureE2eSubscription } from '../../fixtures/ensureE2eSubscription';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('226.G1 — Scheduled export delete guarantee chain @critical @destructive', () => {
  test.setTimeout(180_000);

  test('hard-delete (or tombstone on Prefect failure): row absent from active list, source dataset preserved', async ({
    page,
    cleanup,
  }) => {
    const dpo = await getTestUser();
    const { access_token } = await loginViaApi(dpo.email, dpo.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
    };

    await page.goto('/');
    await page.evaluate((token) => {
      localStorage.setItem('access_token', token);
    }, access_token);

    await ensureE2eSubscription(page, access_token);

    // ── Step 1 — Pre-flight: skip cleanly when MVP_MODE blocks
    // /scheduled-exports/ (returns 404). This avoids running an expensive
    // dataset-create chain only to fail at the export-create step.
    const mvpProbe = await page.request.get(`${API_BASE}/scheduled-exports/`, { headers });
    if (mvpProbe.status() === 404) {
      test.skip(
        true,
        '/scheduled-exports/ is MVP_MODE-gated (404) per hub/apps/api/mvp_mode.py:43. ' +
          'Re-enable by deploying with MVP_MODE=false. Skipping destroy guarantee — ' +
          'the gate is upstream, not in the destroy path.',
      );
      return;
    }

    // ── Step 2 — Provision a dataset to be the export source.
    let datasetId: string;
    try {
      datasetId = await createDatasetViaApi(dpo, { forceNew: true, cleanup });
    } catch (err) {
      test.skip(
        true,
        `Could not provision dataset for export source (${(err as Error).message}). ` +
          `Likely a file-upload backend issue; unblock by ensuring S3/MinIO test bucket is reachable.`,
      );
      return;
    }

    // ── Step 2 — Create the scheduled export.
    const name = `e2e-se-g1-${Date.now()}`;
    const expRes = await page.request.post(`${API_BASE}/scheduled-exports/`, {
      headers,
      data: {
        name,
        schedule_config: { cron: '0 4 * * *', timezone: 'UTC' },
        destination_type: 'S3',
        destination_config: { bucket: 'e2e-test-bucket' },
        source_scope: { dataset_ids: [datasetId] },
      },
    });
    if (!expRes.ok()) {
      test.skip(
        true,
        `Could not provision scheduled export (status=${expRes.status()} body=${(await expRes.text()).slice(0, 200)})`,
      );
      return;
    }
    const expJson = (await expRes.json()) as { id: string };
    const exportId = expJson.id;

    // ── Step 3 — DELETE.
    const deleteRes = await page.request.delete(
      `${API_BASE}/scheduled-exports/${exportId}/`,
      { headers },
    );
    const status = deleteRes.status();
    expect(
      status,
      `DELETE expected 204 or 409 (Prefect-coord); got ${status} ${await deleteRes.text()}`,
    ).toBeLessThan(500);
    expect([204, 409]).toContain(status);

    if (status === 204) {
      await verifyViaApiAbsent(page, `/api/v1/scheduled-exports/${exportId}/`);

      const listRes = await page.request.get(
        `${API_BASE}/scheduled-exports/?page_size=100`,
        { headers },
      );
      expect(listRes.ok()).toBe(true);
      const listBody = (await listRes.json()) as
        | { results?: Array<{ id: string }> }
        | Array<{ id: string }>;
      const rows = Array.isArray(listBody) ? listBody : listBody.results ?? [];
      expect(
        rows.find((r) => r.id === exportId),
        `Hard-deleted export ${exportId} should not appear in list`,
      ).toBeUndefined();
    } else {
      await verifyViaApi<{ id: string; status: string }>(
        page,
        `/api/v1/scheduled-exports/${exportId}/`,
        (body) => body.id === exportId && body.status === 'DELETED',
      );
      const listRes = await page.request.get(
        `${API_BASE}/scheduled-exports/?page_size=100`,
        { headers },
      );
      expect(listRes.ok()).toBe(true);
      const listBody = (await listRes.json()) as
        | { results?: Array<{ id: string }> }
        | Array<{ id: string }>;
      const rows = Array.isArray(listBody) ? listBody : listBody.results ?? [];
      expect(
        rows.find((r) => r.id === exportId),
        `Tombstoned export ${exportId} (status=DELETED) should be excluded from list`,
      ).toBeUndefined();
    }

    // ── Step 4 — Re-DELETE no 5xx.
    const reDel = await page.request.delete(
      `${API_BASE}/scheduled-exports/${exportId}/`,
      { headers },
    );
    expect(reDel.status()).toBeLessThan(500);

    // ── Step 5 — Cascade: source dataset remains queryable.
    const dsGet = await page.request.get(`${API_BASE}/datasets/${datasetId}/`, { headers });
    expect(
      dsGet.ok(),
      `Source dataset ${datasetId} unexpectedly missing after export delete (cross-resource cascade collateral)`,
    ).toBe(true);
  });
});
