/**
 * Phase 260.3.C — File download UI: GET `/files/{id}/download/` → presign → audit `FILE_DOWNLOADED`.
 *
 * Real backend + browser UI. Uses `/files` list + detail modal and row Download action.
 */

import * as crypto from 'node:crypto';
import { expect } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';
import { test } from '../fixtures/test-data-cleanup';
import { fetchAuditEventsForResourceAction, verifyAuditEvent } from '../fixtures/verifyAuditEvent';

async function sleep(ms: number): Promise<void> {
  await new Promise((r) => setTimeout(r, ms));
}

test.describe('File download UI (260.3.C)', () => {
  test.setTimeout(180000);

  test('modal + row Download hit presign API and audit FILE_DOWNLOADED', async ({
    page,
    request,
    cleanup,
  }) => {
    const user = await getTestUser();

    await loginAndNavigateToRoute(page, user, '/files', {
      timeout: 90000,
      contentSelector: '[data-testid="file-list-page"]',
    });

    const token = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(token, 'access_token after login').toBeTruthy();
    const authHeader = {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    };

    const csvBody = Buffer.from('col_a,col_b\n1,2\n');
    const sha256 = crypto.createHash('sha256').update(csvBody).digest('hex');
    const uploadedFileName = `e2e-dl-${Date.now()}.csv`;

    const initResp = await request.post('/api/v1/files/init/', {
      headers: authHeader,
      data: {
        name: uploadedFileName,
        content_type: 'text/csv',
        size: csvBody.length,
        upload_method: 'browser',
      },
    });
    expect(initResp.ok(), await initResp.text()).toBeTruthy();
    const initJson = (await initResp.json()) as {
      file_id: string;
      upload_url: string;
    };

    const putResp = await request.put(initJson.upload_url, {
      headers: { 'Content-Type': 'text/csv' },
      data: csvBody,
    });
    if (!putResp.ok()) {
      const url = new URL(initJson.upload_url);
      const altPort = url.port || '9010';
      const fallback = await request.put(`http://127.0.0.1:${altPort}${url.pathname}${url.search}`, {
        data: csvBody,
        headers: { 'Content-Type': 'text/csv' },
      });
      expect(fallback.ok(), await fallback.text()).toBeTruthy();
    } else {
      expect(putResp.ok(), await putResp.text()).toBeTruthy();
    }

    const completeResp = await request.post(`/api/v1/files/${initJson.file_id}/complete/`, {
      headers: authHeader,
      data: { content_sha256: sha256 },
    });
    expect(completeResp.ok(), await completeResp.text()).toBeTruthy();

    cleanup.track({ type: 'file', id: initJson.file_id, owner: user });

    const deadline = Date.now() + 120000;
    let downloadable = false;
    while (Date.now() < deadline) {
      const meta = await request.get(`/api/v1/files/${initJson.file_id}/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(meta.ok(), await meta.text()).toBeTruthy();
      const metaJson = (await meta.json()) as {
        scan_status?: string;
        status?: string;
      };
      const scan = metaJson.scan_status ?? 'PENDING_SCAN';
      const st = metaJson.status ?? '';
      if (
        (st === 'ACTIVE' || st === 'COMPLETED') &&
        scan !== 'PENDING_SCAN' &&
        scan !== 'INFECTED'
      ) {
        downloadable = true;
        break;
      }
      await sleep(400);
    }
    expect(downloadable, 'file never became downloadable (scan/lifecycle)').toBe(true);

    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="file-list-table"]', { timeout: 60000 });

    await expect(page.getByTestId(`file-list-download-${initJson.file_id}`)).toBeEnabled();

    // noverify: navigation-only — opens the file detail modal; no mutation.
    await page.getByRole('button', { name: uploadedFileName }).click();
    await expect(page.getByRole('heading', { name: /file details/i })).toBeVisible();

    const modalPresign = page.waitForResponse(
      (res) =>
        res.url().includes(`/api/v1/files/${initJson.file_id}/download`) &&
        res.request().method() === 'GET' &&
        res.ok(),
      { timeout: 60000 }
    );
    // noverify: download-presign GET is the action under test; the
    // 200-status assertion + verifyAuditEvent immediately below cover the
    // full mutation contract (the read-only download presign is paired
    // with a FILE_DOWNLOADED audit event by design).
    await page.getByTestId('file-detail-download-btn').click();
    expect((await modalPresign).status()).toBe(200);

    await verifyAuditEvent(page, {
      action: 'FILE_DOWNLOADED',
      resourceType: 'FILE',
      resourceId: initJson.file_id,
    });

    // noverify: closes the file detail modal — no backend mutation fires.
    await page.getByRole('button', { name: /close/i }).click();

    const rowPresign = page.waitForResponse(
      (res) =>
        res.url().includes(`/api/v1/files/${initJson.file_id}/download`) &&
        res.request().method() === 'GET' &&
        res.ok(),
      { timeout: 60000 }
    );
    // noverify: row-level download trigger — the presign GET assertion
    // (rowPresign 200) and the audit-event count assertion below
    // (≥2 FILE_DOWNLOADED rows) together cover the mutation/audit pair.
    await page.getByTestId(`file-list-download-${initJson.file_id}`).click();
    expect((await rowPresign).status()).toBe(200);

    const auditRows = await fetchAuditEventsForResourceAction(
      page,
      initJson.file_id,
      'FILE_DOWNLOADED',
      { pageSize: 25 },
    );
    expect(
      auditRows.length,
      'each UI download should emit FILE_DOWNLOADED (modal + row)',
    ).toBeGreaterThanOrEqual(2);
  });
});
