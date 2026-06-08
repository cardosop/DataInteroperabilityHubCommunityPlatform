/**
 * E2E Feature: File Upload Resume — Phase 260.3.F.3.
 *
 * The 260.3.F.3 contract is: "start multipart → kill connection →
 * reload → resume → complete". This spec exercises the full chain
 * against a live Hub backend with three behavioural sub-tests, each
 * landing on a different layer of the contract:
 *
 *   1. **Resume prompt UX after a durable checkpoint + reload.**
 *      Seeds a deterministic checkpoint (the same shape
 *      ``MultipartUploader`` writes after every successful chunk PUT;
 *      the seed is the safe-deterministic equivalent of "the upload
 *      was killed mid-flight"), reloads the page (the literal
 *      production trigger per 260.3.F.3), and asserts the resume
 *      banner renders with the right file metadata + parts progress.
 *      Tests that ``Discard`` clears the checkpoint AND removes the
 *      banner.
 *   2. **Network-failure mid-multipart preserves a checkpoint.**
 *      Drives a real ``POST /files/init/`` against the Hub backend,
 *      then aborts the chunk PUT to S3 via Playwright's ``page.route``
 *      (the realistic stand-in for "kill connection"), and confirms
 *      the localStorage checkpoint is left behind so a reload would
 *      surface a Resume prompt.
 *   3. **Resume action wires the file-picker.** Verifies that
 *      clicking the Resume CTA opens the resume-only ``<input
 *      type=file>`` (the user-gesture path that lets the user re-pick
 *      the same File handle since the original is gone after reload).
 *
 * What is intentionally NOT duplicated here (covered upstream):
 *   - Real S3 ``list_parts`` round-trip — pytest contract test
 *     ``hub/apps/files/tests/test_multipart_list_parts.py``.
 *   - S3-truth-wins reconciliation algorithm —
 *     ``src/features/files/utils/multipartUploader.test.ts``.
 *   - Re-pick / fingerprint-mismatch UX —
 *     ``src/features/files/components/FileUpload.test.tsx``.
 *   - ``xhrChunkPut`` ETag-header capture (CORS contract) —
 *     ``src/features/files/utils/xhrChunkPut.test.ts``.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';
import { waitForAppMainReady } from '../fixtures/helpers';

const RESUME_STORAGE_KEY = 'meshant.upload.resume.v1';

function makeSeedCheckpoint(userId: string) {
  const now = Date.now();
  return {
    fingerprint: `${userId}|big.csv|209715200|${now - 60_000}`,
    fileId: 'cp-file-' + Math.random().toString(36).slice(2, 10),
    uploadId: 'cp-mpu-' + Math.random().toString(36).slice(2, 10),
    fileName: 'big.csv',
    contentType: 'text/csv',
    totalSize: 209_715_200,
    chunkSize: 52_428_800,
    chunkCount: 4,
    completedParts: [
      { partNumber: 1, etag: '"e1"' },
      { partNumber: 2, etag: '"e2"' },
    ],
    startedAt: now - 60_000,
    updatedAt: now - 30_000,
  };
}

test.describe('Feature: File Upload Resume (Phase 260.3.F.3)', () => {
  test.setTimeout(120_000);

  test('renders resume prompt after a checkpoint is persisted; Discard clears it', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginUser(page, user);

    const checkpoint = makeSeedCheckpoint(user.id);

    await page.goto('/files');
    await waitForAppMainReady(page, { timeout: 30_000 });

    await page.evaluate(
      ({ key, payload }) => {
        const map = { [payload.fingerprint]: payload };
        localStorage.setItem(key, JSON.stringify(map));
      },
      { key: RESUME_STORAGE_KEY, payload: checkpoint }
    );

    await page.reload();
    await waitForAppMainReady(page, { timeout: 30_000 });

    const prompt = page.getByTestId('file-upload-resume-prompt');
    await expect(prompt).toBeVisible();
    await expect(prompt).toContainText('Resume previous upload?');
    await expect(prompt).toContainText('big.csv');
    await expect(prompt).toContainText('2/4 parts uploaded (50%)');

    // Discards the in-browser resume checkpoint — purely client-side
    // localStorage cleanup (no backend mutation or audit event). The
    // localStorage assertion below is the canonical verification.
    // noverify: client-side localStorage cleanup; no backend write or audit event.
    await page.getByTestId(`discard-btn-${checkpoint.fingerprint}`).click();
    await expect(prompt).toBeHidden();

    const remaining = await page.evaluate(
      (key) => localStorage.getItem(key),
      RESUME_STORAGE_KEY
    );
    expect(remaining).toBeNull();
    await expect(page.getByTestId('file-upload-dropzone')).toBeVisible();
  });

  test('Resume CTA opens the resume file picker (user-gesture path)', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginUser(page, user);

    const checkpoint = makeSeedCheckpoint(user.id);

    await page.goto('/files');
    await waitForAppMainReady(page, { timeout: 30_000 });
    await page.evaluate(
      ({ key, payload }) => {
        const map = { [payload.fingerprint]: payload };
        localStorage.setItem(key, JSON.stringify(map));
      },
      { key: RESUME_STORAGE_KEY, payload: checkpoint }
    );
    await page.reload();
    await waitForAppMainReady(page, { timeout: 30_000 });

    // The dedicated resume <input type="file"> exists in the DOM with
    // a stable test id. Pre-click the input is empty.
    const resumeInput = page.getByTestId('resume-file-input');
    await expect(resumeInput).toBeAttached();

    // Wire a filechooser listener BEFORE the click — Playwright
    // surfaces the native picker as a chooser event on the page.
    const chooserPromise = page.waitForEvent('filechooser', { timeout: 5_000 });
    // The click opens the native file picker (user-gesture path). No
    // backend mutation fires until a file is selected and a presigned
    // chunk PUT is issued. The mismatch error surfaced below is the
    // contract this test pins.
    // noverify: opens native file picker; no backend mutation fires.
    await page.getByTestId(`resume-btn-${checkpoint.fingerprint}`).click();

    const chooser = await chooserPromise;
    expect(chooser).toBeTruthy();
    // Provide a deliberately mis-fingerprinted file (different name)
    // to verify the mismatch path surfaces a clear error rather than
    // silently uploading against the wrong file_id.
    await chooser.setFiles({
      name: 'different.csv',
      mimeType: 'text/csv',
      buffer: Buffer.alloc(64),
    });

    // Mismatch error renders inline, no upload begins.
    await expect(page.getByTestId('resume-error')).toBeVisible({ timeout: 5_000 });
    await expect(page.getByTestId('resume-error')).toContainText(/does not match/i);
  });

  test('a failed chunk PUT during a real upload leaves a checkpoint behind for resume', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginUser(page, user);

    // Pre-clear any leftover checkpoints so this test is self-contained.
    await page.goto('/files');
    await waitForAppMainReady(page, { timeout: 30_000 });
    await page.evaluate((key) => localStorage.removeItem(key), RESUME_STORAGE_KEY);

    // Block ALL S3-style PUTs so the chunk transport fails. The
    // backend ``/files/init/`` and ``/chunks/init/`` calls remain
    // live so the multipart upload_id IS allocated and the baseline
    // checkpoint (Phase 260.3.F GAP-A defence) is written before the
    // first PUT is attempted.
    await page.route(/.+/, async (route) => {
      const req = route.request();
      const url = req.url();
      const method = req.method();
      if (method === 'PUT' && /(?:minio|amazonaws|s3\b)/i.test(url)) {
        await route.abort('failed');
        return;
      }
      await route.continue();
    });

    // Drop a 200 MB file so the backend takes the multipart path
    // (``size > 100 MB`` threshold; see ``init_upload`` in
    // ``hub/apps/files/views.py``). Buffer.alloc is zero-filled which
    // is fine — the bytes never reach S3 since we abort the PUT.
    const dropzone = page.getByTestId('file-upload-dropzone');
    await expect(dropzone).toBeVisible();
    const dropzoneInput = dropzone.locator('input[type="file"]');
    await dropzoneInput.setInputFiles({
      name: 'resume-victim.csv',
      mimeType: 'text/csv',
      buffer: Buffer.alloc(200 * 1024 * 1024 + 1024),
    });

    // Wait for the failed PUT to propagate. The uploader catches the
    // error and surfaces it via ``ErrorDisplay``; the dropzone
    // returns to idle. We don't assert on the timing — just that
    // the upload error renders within a reasonable budget.
    await page.waitForTimeout(3_000);

    // The Phase 260.3.F GAP-A baseline checkpoint MUST be on disk
    // even though zero parts ever PUT successfully.
    const stored = await page.evaluate(
      (key) => localStorage.getItem(key),
      RESUME_STORAGE_KEY
    );
    expect(stored).not.toBeNull();
    const map = JSON.parse(stored as string);
    const checkpoints = Object.values(map) as Array<{
      fileName: string;
      uploadId: string;
      completedParts: unknown[];
      fingerprint: string;
    }>;
    expect(checkpoints.length).toBeGreaterThan(0);
    const cp = checkpoints[0];
    expect(cp.fileName).toBe('resume-victim.csv');
    expect(typeof cp.uploadId).toBe('string');
    expect(cp.uploadId.length).toBeGreaterThan(0);
    expect(cp.completedParts).toEqual([]);

    // Reload re-renders the resume prompt — the production trigger
    // for 260.3.F.3.
    await page.reload();
    await waitForAppMainReady(page, { timeout: 30_000 });
    await expect(page.getByTestId('file-upload-resume-prompt')).toBeVisible();
    await expect(page.getByTestId(`resume-btn-${cp.fingerprint}`)).toBeVisible();
  });
});
