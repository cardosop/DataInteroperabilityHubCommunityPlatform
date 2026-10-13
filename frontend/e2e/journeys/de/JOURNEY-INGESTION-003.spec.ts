/**
 * E2E Journey: JOURNEY-INGESTION-003 — Edit and Delete Scheduled Ingestion
 *
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md (Scheduled Operations)
 *
 * The edit/delete surface, exercised for real: the ingestion is created
 * through the UI (real S3 fields), renamed + rescheduled on the edit page,
 * the persistence is asserted against the API (the UI never displays raw
 * source_config), then the deletion is confirmed through the UI and the
 * API agrees (404). Replaces the 276.B.105 deferred stub.
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

test.describe('JOURNEY-INGESTION-003: Edit and Delete Scheduled Ingestion @critical', () => {
  test.setTimeout(180000);

  test('UI edit persists name + schedule; UI delete removes the ingestion', async ({ page }) => {
    skipIfRemoteApi(test, 'Scheduled-ingestion journey requires the local docker stack');
    const tenant = provisionTenant();
    const minio = provisionMinioSource({ bucket: `e2e-ing-${Date.now()}` });

    const token = await login(tenant);
    const user = { email: tenant.email, password: tenant.password } as TestUser;

    // ── Create via the UI (real fields, same flow as INGESTION-001) ────
    // Navigate FIRST: injectTokensBeforeGotoForUser writes localStorage
    // via page.evaluate, which throws on about:blank (SecurityError —
    // swallowed by the fixture), silently leaving the storageState user
    // (default tenant) in control of the SPA's X-Tenant-Id.
    await gotoWithRetry(page, '/');
    await injectTokensBeforeGotoForUser(page, user);
    await gotoWithRetry(page, '/scheduled-ingestions/create');
    await waitForAppMainReady(page);

    await page.getByLabel(/name/i).fill(`edit-delete-e2e-${Date.now()}`);
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

    // ── Edit: rename + reschedule ──────────────────────────────────────
    const editedName = `edit-delete-e2e-edited-${Date.now()}`;
    await page.getByLabel('Edit scheduled ingestion').click();
    await expect(page.getByTestId('scheduled-ingestion-edit-page')).toBeVisible({
      timeout: 15000,
    });
    await page.getByLabel(/name/i).fill(editedName);
    await page.getByLabel(/schedule type/i).selectOption('WEEKLY');
    await page.getByRole('button', { name: /update/i }).click();

    // Back on the detail page — the new name is rendered.
    await expect(page.getByText(editedName).first()).toBeVisible({ timeout: 15000 });

    // API agrees (the authoritative check — the UI never shows source_config).
    const auth = { Authorization: `Bearer ${token}` };
    const detailResp = await fetchWithRetry(
      `${API_BASE_URL}/scheduled-ingestions/${ingestionId}/`,
      { headers: auth }
    );
    expect(detailResp.status, `detail fetch: ${detailResp.status}`).toBe(200);
    const detail = (await detailResp.json()) as { name?: string; schedule_type?: string };
    expect(detail.name).toBe(editedName);
    expect(detail.schedule_type).toBe('WEEKLY');

    // ── Delete through the UI ──────────────────────────────────────────
    await page.getByLabel('Delete scheduled ingestion').click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 10000 });
    await dialog.getByRole('button', { name: 'Delete' }).click();

    await page.waitForURL(/\/scheduled-ingestions$/, { timeout: 30000 });
    await waitForAppMainReady(page);
    await expect(page.getByText(editedName)).toHaveCount(0);

    // The API agrees: the row is gone.
    const afterDelete = await fetchWithRetry(
      `${API_BASE_URL}/scheduled-ingestions/${ingestionId}/`,
      { headers: auth }
    );
    expect(afterDelete.status, `deleted ingestion still reachable: ${afterDelete.status}`).toBe(
      404
    );
  });
});
