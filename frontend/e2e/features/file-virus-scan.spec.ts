/**
 * Phase 260.2.D — EICAR upload, INFECTED scan status, download 403, dataset create 403.
 *
 * Opt-in: set RUN_FILE_VIRUS_SCAN_E2E=1 when Playwright runs against a stack where
 * `clamav-test` is reachable from the API and MinIO uploads succeed (same as backend E2E).
 *
 * Uses repo fixture `tests/fixtures/eicar.txt` (safe test vector for AV engines).
 */

import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../fixtures/helpers';

const RUN_E2E = process.env.RUN_FILE_VIRUS_SCAN_E2E === '1';

// Playwright runs specs as ESM modules; ``__filename`` is a CommonJS-only
// global and is undefined here. Recover it from ``import.meta.url`` —
// matches the canonical pattern in ``dimensions/openapi-drift.spec.ts``.
const __filename = fileURLToPath(import.meta.url);

const EICAR_PATH = path.resolve(
  path.dirname(__filename),
  '..',
  '..',
  '..',
  'tests',
  'fixtures',
  'eicar.txt'
);

test.describe('File virus scan (EICAR)', () => {
  test.skip(!RUN_E2E, 'Set RUN_FILE_VIRUS_SCAN_E2E=1 with API + ClamAV + MinIO (Phase 260.2.D)');
  test.setTimeout(240000);

  test('upload EICAR → poll INFECTED → download and dataset creation forbidden', async ({
    page,
    request,
  }) => {
    const uploadedFileName = `eicar-${Date.now()}.csv`;

    const user = await getTestUser();
    await loginUser(page, user);

    const token = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(token, 'access_token after login').toBeTruthy();
    const authHeader = { Authorization: `Bearer ${token}` };

    const eicarBody = fs.readFileSync(EICAR_PATH);
    const sha256 = crypto.createHash('sha256').update(eicarBody).digest('hex');

    const initResp = await request.post('/api/v1/files/init/', {
      headers: authHeader,
      data: {
        name: uploadedFileName,
        content_type: 'text/csv',
        size: eicarBody.length,
        upload_method: 'browser',
      },
    });
    expect(initResp.ok(), `file init ${initResp.status()}`).toBeTruthy();
    const initJson = (await initResp.json()) as {
      file_id?: string;
      id?: string;
      upload_url?: string;
    };
    const fileId = initJson.file_id ?? initJson.id;
    expect(fileId).toBeTruthy();

    if (initJson.upload_url) {
      const putResp = await request.put(initJson.upload_url, {
        data: eicarBody,
        headers: { 'Content-Type': 'text/csv' },
      });
      if (!putResp.ok()) {
        const url = new URL(initJson.upload_url);
        const altPort = url.port || '9010';
        await request.put(`http://127.0.0.1:${altPort}${url.pathname}${url.search}`, {
          data: eicarBody,
          headers: { 'Content-Type': 'text/csv' },
        });
      }
    }

    const completeResp = await request.post(`/api/v1/files/${fileId}/complete/`, {
      headers: { ...authHeader, 'Content-Type': 'application/json' },
      data: { content_sha256: sha256 },
    });
    expect(completeResp.ok(), `complete ${completeResp.status()}`).toBeTruthy();

    const deadline = Date.now() + 180000;
    let scanStatus = '';
    while (Date.now() < deadline) {
      const meta = await request.get(`/api/v1/files/${fileId}/`, { headers: authHeader });
      expect(meta.ok(), `file retrieve ${meta.status()}`).toBeTruthy();
      const metaJson = (await meta.json()) as { scan_status?: string };
      scanStatus = metaJson.scan_status ?? '';
      if (scanStatus === 'INFECTED') break;
      if (
        scanStatus &&
        scanStatus !== 'PENDING_SCAN' &&
        scanStatus !== 'INFECTED'
      ) {
        throw new Error(`Unexpected scan_status while polling: ${scanStatus}`);
      }
      await new Promise((r) => setTimeout(r, 400));
    }
    expect(scanStatus).toBe('INFECTED');

    const dl = await request.get(`/api/v1/files/${fileId}/download/`, {
      headers: authHeader,
    });
    expect(dl.status()).toBe(403);
    const dlJson = (await dl.json()) as { code?: string };
    expect(dlJson.code).toBe('FILE_INFECTED');

    const ds = await request.post('/api/v1/datasets/', {
      headers: authHeader,
      data: { file_id: fileId },
    });
    expect(ds.status()).toBe(403);
    const dsJson = (await ds.json()) as { code?: string };
    expect(dsJson.code).toBe('FILE_INFECTED');

    await loginAndNavigateToRoute(page, user, '/files', {
      timeout: 60000,
      contentSelector: '[data-testid="file-list-page"]',
    });
    await waitForLoadingComplete(page, { timeout: 30000 });

    const infectedPill = page
      .locator(`tr[data-file-name="${uploadedFileName}"]`)
      .locator('[data-scan-status="INFECTED"]');
    await expect(infectedPill).toBeVisible({ timeout: 120000 });
  });
});
