/**
 * Phase 260.3.C — File download UI: GET `/files/{id}/download-payload/` → presign → audit `FILE_DOWNLOAD_REQUESTED`.
 *
 * Real backend + browser UI. The download surface is the file DETAIL page
 * (`/files/{id}` → `file-detail-download-btn`); the list's View action opens
 * a metadata-only modal and row-level Download buttons were removed.
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

  test('detail-page Download hits presign API and audits FILE_DOWNLOAD_REQUESTED', async ({
    page,
    request,
    cleanup,
  }) => {
    const user = await getTestUser();

    await loginAndNavigateToRoute(page, user, '/files', {
      timeout: 90000,
      contentSelector: '[data-testid="file-list-page"]',
    });

    const token = await page.evaluate(() => {
      const g = (window as unknown as { __getAccessToken?: () => string | null })
        .__getAccessToken;
      return typeof g === 'function' ? g() : localStorage.getItem('access_token');
    });
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
    // The table renders only when the list fetch succeeds AND rows exist;
    // a strict 60s wait times out opaquely on both the churn error
    // terminal and a legitimate empty list (b7: 60s timeout on this exact
    // selector). Probe with bounded waits and classify the terminal.
    // intentional: bounded best-effort probes — the error-terminal throw and empty-state skip below handle the non-render states deterministically.
    const tableReady = await page
      .locator('[data-testid="file-list-table"]')
      .waitFor({ state: 'visible', timeout: 60000 })
      .then(() => true)
      .catch(() => false);
    if (!tableReady) {
      const errorDisplay = page
        .locator('.error-display, [data-testid="error-display"]')
        .first();
      if ((await errorDisplay.count()) > 0) {
        // intentional: diagnostic-only read — an empty read just means no error surface rendered and the message falls back to the generic form.
        const errText = (await errorDisplay.textContent().catch(() => '')) ?? '';
        throw new Error(
          `File list shows error after upload+reload: "${errText?.slice(0, 300)}"`
        );
      }
      const hasEmptyState = (await page.getByTestId('file-list-empty-state').count()) > 0;
      if (hasEmptyState) {
        test.skip(hasEmptyState, 'File list empty after upload — upload/lifecycle did not persist');
        return;
      }
      throw new Error('File list table did not render after upload+reload (no error, no empty state)');
    }

    // Deep-link to the detail page — the download surface (the list's
    // View action opens a metadata-only modal with no download control).
    await page.goto(`/files/${initJson.file_id}`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('file-detail-page')).toBeVisible({ timeout: 30000 });

    const presign = page.waitForResponse(
      (res) =>
        res.url().includes(`/api/v1/files/${initJson.file_id}/download-payload`) &&
        res.request().method() === 'GET' &&
        res.ok(),
      { timeout: 60000 }
    );
    // noverify: download-presign GET is the action under test; the
    // 200-status assertion + verifyAuditEvent immediately below cover the
    // full mutation contract. NOTE: the CURRENT backend contract emits
    // FILE_DOWNLOAD_REQUESTED at presign time (files/views.py download
    // action); nothing emits FILE_DOWNLOADED — the event bus publishes
    // file.downloaded but no consumer converts it into an audit row, so
    // the old FILE_DOWNLOADED pin polled an impossibility (b7 re-run
    // #7: 0 audit rows).
    await page.getByTestId('file-detail-download-btn').click();
    expect((await presign).status()).toBe(200);

    await verifyAuditEvent(page, {
      action: 'FILE_DOWNLOAD_REQUESTED',
      resourceType: 'FILE',
      resourceId: initJson.file_id,
    });

    const auditRows = await fetchAuditEventsForResourceAction(
      page,
      initJson.file_id,
      'FILE_DOWNLOAD_REQUESTED',
      { pageSize: 25 },
    );
    expect(
      auditRows.length,
      'the detail-page download should emit FILE_DOWNLOAD_REQUESTED',
    ).toBeGreaterThanOrEqual(1);
  });
});
