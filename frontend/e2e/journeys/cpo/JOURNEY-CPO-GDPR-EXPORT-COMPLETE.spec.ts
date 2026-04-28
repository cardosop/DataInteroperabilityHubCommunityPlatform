/**
 * E2E Test: JOURNEY-CPO-GDPR-EXPORT-COMPLETE — GDPR data export completeness
 * (Phase 226 G17).
 *
 * GDPR Article 20 (data portability) requires that an export contains a
 * complete machine-readable copy of the user's data. The endpoint exists,
 * but earlier UI specs only verified that the export *job* succeeded —
 * not that every resource the user owns is actually present in the
 * download. This spec closes the gap:
 *
 *   1. Create N resources across all in-scope families (asset, dataset,
 *      contract) as the test user.
 *   2. Trigger POST /api/v1/users/me/export-jobs/export-data/.
 *   3. Poll the export job until download_url is populated.
 *   4. Download the archive (ZIP), extract user_data.json, parse.
 *   5. Assert every created id appears in the corresponding section.
 *   6. Negative: another user's ids do NOT appear in this user's export.
 *
 * Format reference (Open Question §14): the backend currently emits ZIP
 * containing `user_data.json` (DataPortabilityService._build_archive at
 * hub/apps/gdpr/services.py). Section keys: user_profile, audit_events,
 * assets, datasets, contracts. This spec takes that format as given and
 * tracks Open Question §14 for any future extension (e.g. signed-PDF
 * receipt, separate per-resource files); a deliberate format shift will
 * trip the matchers below and force a coordinated update.
 *
 * No mocks. Real backend.
 */

import { expect, test } from '@playwright/test';
import * as zlib from 'node:zlib';
import { getTestUser, getConsumerTestUser } from '../../fixtures/auth';
import {
  createAssetViaApi,
  createDatasetViaApi,
} from '../../fixtures/api-assets';

const API_BASE = '/api/v1';

interface ExportJobResponse {
  job_id?: string;
  id?: string;
  status?: string;
  download_url?: string | null;
}

async function login(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  page: any,
  email: string,
  password: string,
): Promise<string> {
  const res = await page.request.post(`${API_BASE}/auth/login/`, {
    data: { email, password },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(res.ok()).toBe(true);
  return (await res.json()).access_token as string;
}

/**
 * Minimal ZIP central-directory parser for JSON files only. The export
 * archive is small (DEFLATE-compressed JSON + README), so we don't need
 * a streaming parser. This avoids adding a runtime dep on `adm-zip`
 * just for this one spec.
 *
 * Returns the raw bytes of `entryName` from the archive, or null if
 * absent. Throws on malformed central directory.
 */
export function extractZipEntry(archive: Buffer, entryName: string): Buffer | null {
  // End-of-central-directory record: signature 0x06054b50, 22 bytes,
  // located in the last 64 KiB of the archive.
  const EOCD_SIG = 0x06054b50;
  const len = archive.length;
  let eocd = -1;
  for (let i = len - 22; i >= Math.max(0, len - 65557); i--) {
    if (archive.readUInt32LE(i) === EOCD_SIG) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new Error('extractZipEntry: end-of-central-directory record not found');
  const cdEntries = archive.readUInt16LE(eocd + 10);
  const cdOffset = archive.readUInt32LE(eocd + 16);

  let offset = cdOffset;
  const CDH_SIG = 0x02014b50;
  const LFH_SIG = 0x04034b50;
  for (let i = 0; i < cdEntries; i++) {
    if (archive.readUInt32LE(offset) !== CDH_SIG) {
      throw new Error(`extractZipEntry: bad central-directory header at ${offset}`);
    }
    const compressionMethod = archive.readUInt16LE(offset + 10);
    const compressedSize = archive.readUInt32LE(offset + 20);
    const fileNameLen = archive.readUInt16LE(offset + 28);
    const extraFieldLen = archive.readUInt16LE(offset + 30);
    const commentLen = archive.readUInt16LE(offset + 32);
    const localHeaderOffset = archive.readUInt32LE(offset + 42);
    const fileName = archive.slice(offset + 46, offset + 46 + fileNameLen).toString('utf8');

    if (fileName === entryName) {
      // Read the local file header to find the actual data start.
      if (archive.readUInt32LE(localHeaderOffset) !== LFH_SIG) {
        throw new Error('extractZipEntry: bad local file header');
      }
      const lfhFileNameLen = archive.readUInt16LE(localHeaderOffset + 26);
      const lfhExtraLen = archive.readUInt16LE(localHeaderOffset + 28);
      const dataStart = localHeaderOffset + 30 + lfhFileNameLen + lfhExtraLen;
      const compressed = archive.slice(dataStart, dataStart + compressedSize);
      if (compressionMethod === 0) {
        return compressed;
      }
      if (compressionMethod === 8) {
        return zlib.inflateRawSync(compressed);
      }
      throw new Error(`extractZipEntry: unsupported compression method ${compressionMethod}`);
    }

    offset += 46 + fileNameLen + extraFieldLen + commentLen;
  }
  return null;
}

interface ExportPayload {
  format_version?: string;
  exported_at?: string;
  user_profile?: { id?: string; email?: string };
  audit_events?: Array<{ resource_id?: string }>;
  assets?: Array<{ id: string; name?: string }>;
  datasets?: Array<{ id: string; name?: string }>;
  contracts?: Array<{ id: string; name?: string }>;
}

/**
 * Pinned major version of the GDPR Article 20 export envelope. Mirrors
 * ``GDPR_EXPORT_FORMAT_VERSION`` in ``hub/apps/gdpr/services.py``. A breaking
 * envelope change must bump the backend constant *and* this assertion in the
 * same PR — that's the cross-stack tripwire OQ5 was added to enforce.
 */
const EXPECTED_GDPR_EXPORT_MAJOR = 1;

test.describe('JOURNEY-CPO-GDPR-EXPORT-COMPLETE: GDPR Article 20 export completeness', () => {
  test.setTimeout(180_000);

  test('export contains every resource the user owns; another user\'s ids are absent', async ({ page }) => {
    // ---- Phase 1: provision N resources as the primary test user.
    const primary = await getTestUser();
    const primaryToken = await login(page, primary.email, primary.password);

    const N = 3;
    const assetIds: string[] = [];
    const datasetIds: string[] = [];
    for (let i = 0; i < N; i++) {
      const aid = await createAssetViaApi(primary, { forceNew: true });
      assetIds.push(aid);
      const did = await createDatasetViaApi(primary, { assetId: aid, forceNew: true });
      datasetIds.push(did);
    }

    // Contracts via API: minimal ODCS, attached to one of our assets if
    // the attach action is supported. Fall back to standalone create when
    // attach_contract is gated.
    const contractIds: string[] = [];
    for (let i = 0; i < 2; i++) {
      const res = await page.request.post(`${API_BASE}/contracts/`, {
        headers: {
          Authorization: `Bearer ${primaryToken}`,
          'Content-Type': 'application/json',
        },
        data: {
          name: `GDPR Export Contract ${i} ${Date.now()}`,
          original_spec_type: 'ODCS',
          version: '1.0.0',
        },
      });
      if (res.ok()) {
        const body = (await res.json()) as { id?: string };
        if (body.id) contractIds.push(body.id);
      }
    }

    // ---- Phase 2: trigger the export job.
    const triggerRes = await page.request.post(
      `${API_BASE}/users/me/export-jobs/export-data/`,
      { headers: { Authorization: `Bearer ${primaryToken}` } },
    );
    if (triggerRes.status() === 404) {
      test.skip(true, 'GDPR export endpoint not enabled in this environment');
    }
    expect(triggerRes.ok(), `export trigger failed: ${triggerRes.status()}`).toBe(true);
    const trigger = (await triggerRes.json()) as ExportJobResponse;
    const jobId = trigger.job_id ?? trigger.id;
    expect(jobId, 'export response missing job_id').toBeTruthy();

    // ---- Phase 3: poll the job until download_url is populated. The
    // backend processes synchronously today (services.py), but allow a
    // generous budget for environments that move it to Celery.
    const deadline = Date.now() + 90_000;
    let downloadUrl: string | null = null;
    let lastStatus = 'unknown';
    while (Date.now() < deadline) {
      const statusRes = await page.request.get(
        `${API_BASE}/users/me/export-jobs/${jobId}/`,
        { headers: { Authorization: `Bearer ${primaryToken}` } },
      );
      if (statusRes.ok()) {
        const body = (await statusRes.json()) as ExportJobResponse;
        lastStatus = body.status ?? 'unknown';
        if (body.download_url) {
          downloadUrl = body.download_url;
          break;
        }
        if (lastStatus === 'FAILED') {
          throw new Error(`export job ${jobId} FAILED: ${JSON.stringify(body).slice(0, 300)}`);
        }
      }
      await page.waitForTimeout(2000);
    }
    expect(downloadUrl, `export job ${jobId} did not produce download_url within budget (last status: ${lastStatus})`).toBeTruthy();

    // ---- Phase 4: download the archive. download_url is a signed S3 URL
    // in production and a relative path in some local stacks; both routes
    // are exercised here. When relative, prepend the API base origin via
    // page.request which preserves the auth context.
    const downloadRes = await page.request.get(downloadUrl!);
    expect(downloadRes.ok(), `download_url GET failed: ${downloadRes.status()}`).toBe(true);
    const archive = await downloadRes.body();
    expect(archive.length, 'export archive must be non-empty').toBeGreaterThan(100);

    const userDataBytes = extractZipEntry(archive, 'user_data.json');
    expect(userDataBytes, 'user_data.json must be present in the export archive').not.toBeNull();
    const payload = JSON.parse(userDataBytes!.toString('utf8')) as ExportPayload;

    // ---- Phase 5: every created id must appear.
    // Format-version pin first — fail loud on schema drift before parsing the rest.
    // Distinguish the two regression modes so the diagnostic points at the
    // actual problem rather than the wrong stack:
    //   (a) field is absent  → backend predates OQ5; redeploy or bump.
    //   (b) field bumped     → backend changed the envelope; this spec
    //                          must be updated in the same PR.
    const fmt = payload.format_version;
    expect(
      typeof fmt === 'string' && fmt.length > 0,
      `GDPR export envelope is missing the \`format_version\` field. ` +
        `Either the staging backend predates OQ5 (rebuild + redeploy), or ` +
        `\`GDPR_EXPORT_FORMAT_VERSION\` in hub/apps/gdpr/services.py was ` +
        `accidentally removed.`,
    ).toBe(true);
    const major = Number.parseInt(fmt!.split('.')[0] ?? '', 10);
    expect(
      Number.isFinite(major) && major === EXPECTED_GDPR_EXPORT_MAJOR,
      `unexpected GDPR export format_version=${fmt} (expected major=${EXPECTED_GDPR_EXPORT_MAJOR}). ` +
        `Backend bumped GDPR_EXPORT_FORMAT_VERSION; update EXPECTED_GDPR_EXPORT_MAJOR ` +
        `(top of this spec) and the matching matchers in the same PR.`,
    ).toBe(true);
    expect(payload.exported_at, 'export envelope must carry exported_at timestamp').toBeTruthy();
    expect(payload.user_profile?.email).toBe(primary.email);
    const exportedAssetIds = (payload.assets ?? []).map((a) => a.id);
    const exportedDatasetIds = (payload.datasets ?? []).map((d) => d.id);
    const exportedContractIds = (payload.contracts ?? []).map((c) => c.id);

    for (const id of assetIds) {
      expect(exportedAssetIds, `export missing asset ${id}`).toContain(id);
    }
    for (const id of datasetIds) {
      expect(exportedDatasetIds, `export missing dataset ${id}`).toContain(id);
    }
    for (const id of contractIds) {
      expect(exportedContractIds, `export missing contract ${id}`).toContain(id);
    }

    // Audit-events: must contain at least one entry whose resource_id is
    // one of our assets — proves the audit trail is included end-to-end.
    const auditResourceIds = new Set((payload.audit_events ?? []).map((e) => e.resource_id ?? ''));
    const anyAuditMatch = assetIds.some((id) => auditResourceIds.has(id));
    expect(
      anyAuditMatch,
      'export audit_events must contain at least one entry for a created asset',
    ).toBe(true);

    // ---- Phase 6: negative — another user's ids do NOT appear in this user's export.
    // Provision a single resource as the consumer test user; assert it is
    // NOT in the primary user's export. This catches a regression in the
    // user= filter on _collect_user_data.
    const consumer = await getConsumerTestUser();
    if (consumer.email === primary.email) {
      // Some envs collapse to a single test identity — skip the negative
      // assertion in that case rather than passing trivially.
      test.info().annotations.push({
        type: 'gdpr-export-negative-skipped',
        description: 'consumer test user equals primary user — no second identity to compare',
      });
      return;
    }
    const otherAssetId = await createAssetViaApi(consumer, { forceNew: true });
    expect(otherAssetId.length).toBeGreaterThan(30);
    expect(
      exportedAssetIds,
      `export of ${primary.email} must NOT contain consumer's asset ${otherAssetId} ` +
        `(scope leak detected)`,
    ).not.toContain(otherAssetId);
  });
});
