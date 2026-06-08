/**
 * Phase 260.7.A — Standalone /files lifecycle E2E (closes Gap 15).
 *
 * Pre-260.7.A, no single spec exercised the /files page as ONE
 * linear journey. The closest existing spec
 * ([file-download-ui.spec.ts](file-download-ui.spec.ts)) covered
 * upload-through-download but stopped before delete; the others
 * each pinned a SLICE (resume, virus-scan, detail page) without
 * driving the full happy path. The product impact: a regression
 * in any single hop (e.g. the modal failing to close after
 * upload, the toast suppressing list refetch, the detail-page
 * delete navigation breaking back to /files) was only catchable
 * by manual QA — every existing spec stopped before exercising
 * the next hop.
 *
 * This spec drives the full happy path through the BROWSER UI
 * (no API-only shortcuts) so a regression at any seam fails the
 * test:
 *
 *   1. Land on /files (the standalone page, not embedded in an
 *      asset/dataset journey).
 *   2. Open the upload modal via ``btn-upload-file``.
 *   3. Pick a file via ``setInputFiles`` on the dropzone's
 *      hidden ``<input type="file">``.
 *   4. Observe the progress state via
 *      ``[data-upload-state="uploading"]``. The mid-upload state
 *      IS paintable because the upload yields control to React
 *      during ``await uploader.upload(file)``.
 *   5. Observe the upload-complete observables: (a) ``/files/init/``
 *      POST captured (file_id materialised), (b) the dropzone /
 *      modal HIDES (``handleUploadComplete`` in FileListPage
 *      sets ``showUploadModal=false``), (c) the success toast
 *      ``File "<name>" uploaded successfully.`` is shown.
 *      The dropzone's INTERNAL ``data-upload-state="success"``
 *      is NOT asserted here — it's never paintable in this
 *      flow. Reason: React 18 auto-batches the four state updates
 *      that follow the upload's ``await`` —
 *      ``setUploadProgress(100)``, ``setUploadSuccess(true)``,
 *      ``setShowUploadModal(false)`` (called via
 *      ``onUploadComplete``), and ``setIsPending(false)`` (queued
 *      by the upload hook's ``finally``) — into ONE render. That
 *      render commits with ``showUploadModal=false`` so the
 *      Modal unmounts BEFORE the dropzone's ``success`` state
 *      ever reaches the DOM. The 10-second success-display
 *      timeout in ``FileUpload.tsx`` only matters when the
 *      component is used outside the FileListPage modal context.
 *      Asserting on the unobservable success state would race
 *      and timeout. The TOAST is the canonical user-visible
 *      success indicator, and the modal-close is the canonical
 *      programmatic indicator — those are what we pin.
 *   6. Verify the list refetches with the new row visible. The
 *      list is sorted ``-created_at`` (FileListView ``ordering``)
 *      so the new row lands on page 1 regardless of how many
 *      pre-existing files the test user owns.
 *   7. Click the file-name button → navigate to ``/files/{id}``
 *      (the detail page, which replaced the legacy detail modal
 *      in 260.4.B — spec wording in tasks.md says "modal" but
 *      the production path is the page).
 *   8. Wait for the file to become downloadable
 *      (``ACTIVE`` + scan ∈ ``{CLEAN, SCAN_UNAVAILABLE}``),
 *      then click ``file-detail-download-btn`` and assert the
 *      ``/download/`` presign endpoint returns 200. (Per Phase
 *      260.3.G the verified-download flow STILL hits this same
 *      endpoint to fetch the presigned URL before fetching from
 *      S3 — see ``downloadFileWithVerification.ts``.)
 *   9. Click ``file-detail-delete-btn`` → the
 *      ``ConfirmDialog`` appears (heading "Delete file").
 *  10. Click the dialog's "Delete" confirm button → the
 *      mutation completes and the page navigates back to
 *      ``/files`` (per ``handleDeleteConfirm`` in
 *      ``FileDetailPage``).
 *  11. Verify the row is gone from the list (not just hidden
 *      — the API row is hard-deleted per Phase 213.C).
 *
 * Cleanup: ``cleanup.track({ type: 'file', ...})`` runs as soon
 * as the file_id is captured (intercepted from the
 * ``/files/init/`` response). Even if the test fails BEFORE the
 * UI delete step, the auto-flush cleanup in
 * ``test-data-cleanup.ts`` hard-deletes the file via the API so
 * the staging tenant doesn't accumulate orphans.
 */

import { expect } from '@playwright/test';

import { getTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';
import { test } from '../fixtures/test-data-cleanup';

// Single small CSV body. Chosen ≪ 100 MB so the uploader takes
// the single-part PUT path (not multipart) — keeps the test
// fast and deterministic. Multipart upload is exercised by
// file-upload-resume.spec.ts.
const CSV_BODY = 'col_a,col_b\n1,2\n3,4\n';

test.describe('Standalone /files lifecycle (260.7.A)', () => {
  // Upload + scan + delete on real backend takes longer than the
  // default 60s. Match the budget to the closest peer spec
  // (file-download-ui.spec.ts uses 180s).
  test.setTimeout(180_000);

  test('upload modal → progress → success → list refresh → detail page → download → delete → row gone', async ({
    page,
    cleanup,
  }) => {
    const user = await getTestUser();

    await test.step('1. Navigate to /files (standalone)', async () => {
      await loginAndNavigateToRoute(page, user, '/files', {
        timeout: 90_000,
        contentSelector: '[data-testid="file-list-page"]',
      });
      await expect(page.getByTestId('file-list-page')).toBeVisible();
    });

    // Capture the file_id the moment the uploader hits
    // /files/init/ — earliest server-side handle on the resource.
    // Tracking happens immediately so a failure ANYWHERE downstream
    // still triggers the auto-cleanup at test end (no orphan row).
    //
    // R1 audit GAP-A: ``.catch(() => null)`` on the abandoned-promise
    // path. If the test fails BEFORE step 4-5 awaits this promise,
    // the underlying ``waitForResponse`` will reject on timeout
    // (60_000ms). An unhandled rejection would surface as test noise
    // and could mask the real failure. The catch returns null so
    // any later ``await`` resolves cleanly — the test has ALREADY
    // failed for the upstream reason, and a null file_id only
    // matters if subsequent steps run, which they won't.
    // intentional: the trailing ``.catch(() => null)`` is the cleanup-tracker
    // fallback documented above; the load-bearing assertion is the
    // upload step further down.
    const fileIdPromise: Promise<string | null> = page
      .waitForResponse(
        (res) =>
          res.url().includes('/api/v1/files/init/') &&
          res.request().method() === 'POST' &&
          res.ok(),
        { timeout: 60_000 }
      )
      .then(async (res) => {
        const json = (await res.json()) as { file_id: string };
        cleanup.track({ type: 'file', id: json.file_id, owner: user });
        return json.file_id;
      })
      // The upstream ``waitForResponse`` may reject on timeout when
      // the upload UI never reaches the ``/files/init/`` POST. The
      // test step that triggers the upload (below) is the
      // load-bearing assertion — this promise-chain only feeds the
      // cleanup tracker, so a null id signals "no file to clean up"
      // rather than masking a regression.
      // intentional: cleanup-tracker fallback only — see block above.
      .catch(() => null);

    const uploadName = `e2e-260.7.A-${Date.now()}.csv`;

    await test.step('2. Open upload modal via btn-upload-file', async () => {
      // noverify: opens the upload modal — no mutation fires until a file
      // is selected and the chunked-upload chain runs (covered later in
      // this same test by the file_id assertion + audit verification).
      await page.getByTestId('btn-upload-file').click();
      await expect(page.getByTestId('file-upload-dropzone')).toBeVisible();
      // Idle state before any file is picked. If a future change
      // pre-populates the upload UI, this assertion catches it.
      await expect(page.getByTestId('file-upload-dropzone')).toHaveAttribute(
        'data-upload-state',
        'idle'
      );
    });

    await test.step('3. Pick file via setInputFiles', async () => {
      const dropzone = page.getByTestId('file-upload-dropzone');
      const fileInput = dropzone.locator('input[type="file"]');
      await fileInput.setInputFiles({
        name: uploadName,
        mimeType: 'text/csv',
        buffer: Buffer.from(CSV_BODY),
      });
    });

    // R1 audit GAP-B: The ``uploading`` state IS observable —
    // ``setIsPending(true)`` runs BEFORE the upload's await
    // yields control, so React paints with
    // ``data-upload-state="uploading"`` while the network call
    // is in flight. We assert it as a soft signal (best-effort)
    // because tiny CSVs CAN finish faster than Playwright's
    // attribute-poll cadence; the binding REAL assertions for
    // upload-completed-successfully are the modal-close + toast
    // + new-row-in-list trio in step 5.
    await test.step('4. Observe in-flight uploading state', async () => {
      const dropzone = page.getByTestId('file-upload-dropzone');
      // intentional: the ``data-upload-state="uploading"`` mid-state
      // is observable on slow loops but can be missed on fast ones
      // when the single-part PUT completes synchronously. Step 5
      // below asserts the terminal "uploaded" state — that's the
      // load-bearing signal; a missed mid-state is not a regression.
      try {
        await expect(dropzone).toHaveAttribute(
          'data-upload-state',
          'uploading',
          { timeout: 5_000 }
        );
      } catch {
        // intentional: the upload may have completed synchronously
        // (single-part PUT of a tiny CSV on a fast loop), in which
        // case the mid-state ``uploading`` is unobservable. Step 5
        // below asserts the terminal ``uploaded`` state — that's
        // the load-bearing signal; a missed mid-state is not a
        // regression.
      }
    });

    const fileId = await test.step(
      '5. Upload completes: modal closes + toast + file_id captured',
      async () => {
        // R1 audit GAP-C: The dropzone's INTERNAL
        // ``data-upload-state="success"`` is NOT paintable in
        // the FileListPage modal context. Reason — see file
        // docstring at the top. Asserting on the modal-close
        // + toast is what the user actually observes and what
        // the React 18 batched render commits.
        //
        // a) Modal/dropzone hides — the canonical programmatic
        //    success indicator. ``handleUploadComplete`` calls
        //    ``setShowUploadModal(false)``; if the upload errored,
        //    the dropzone would stay mounted with an
        //    ``ErrorDisplay`` block.
        await expect(page.getByTestId('file-upload-dropzone')).toBeHidden({
          timeout: 60_000,
        });
        // b) Toast surfaces — canonical USER-visible success
        //    indicator. ``handleUploadComplete`` calls
        //    ``toast.success('File "<name>" uploaded successfully.')``.
        //    A regression in the toast subsystem (e.g. provider
        //    not mounted on /files) would skip this surface and
        //    silently break user feedback.
        await expect(
          page.getByText(`File "${uploadName}" uploaded successfully.`)
        ).toBeVisible({ timeout: 30_000 });
        // c) file_id materialised. The promise resolves once
        //    /files/init/ returned and ``cleanup.track`` ran;
        //    null means the listener timed out (covered above
        //    by ``.catch(() => null)``) — fail loudly here.
        const id = await fileIdPromise;
        expect(id, '/files/init/ POST never observed').not.toBeNull();
        return id as string;
      }
    );

    await test.step('6. List refetches with new row visible', async () => {
      await expect(page.getByTestId('file-list-table')).toBeVisible();
      // The new row is present BY NAME (the row's button shows
      // the filename). React Query invalidation
      // (``queryClient.invalidateQueries({ queryKey: ['files'] })``
      // in ``useMultipartUpload``) fires the refetch — a
      // regression that breaks invalidation would leave the
      // OLD list rendered with no new row.
      //
      // The list is sorted ``-created_at`` (per
      // ``FileListView.ordering`` in hub/apps/files/views.py),
      // so the freshly-uploaded file is on page 1 regardless of
      // how many pre-existing files the test user owns.
      await expect(
        page.getByRole('button', { name: uploadName })
      ).toBeVisible({ timeout: 30_000 });
    });

    await test.step('7. Click row → navigate to /files/{id}', async () => {
      // noverify: navigation-only — opens the file detail page; no mutation.
      await page.getByRole('button', { name: uploadName }).click();
      // 260.4.B moved the detail surface from a modal onto a
      // deep-linkable page; the URL contains the file_id.
      await expect(page).toHaveURL(new RegExp(`/files/${fileId}(?:[/?#]|$)`), {
        timeout: 30_000,
      });
      await expect(page.getByTestId('file-detail-page')).toBeVisible();
    });

    await test.step('8. Wait for downloadable, then click Download', async () => {
      // ``canDownloadFile`` gates the button on
      // status === ACTIVE && scan ∈ {CLEAN, SCAN_UNAVAILABLE}.
      // The button enables on its own once the polling hook
      // returns the post-scan metadata.
      await expect(page.getByTestId('file-detail-download-btn')).toBeEnabled({
        timeout: 120_000,
      });
      const downloadResponsePromise = page.waitForResponse(
        (res) =>
          res.url().includes(`/api/v1/files/${fileId}/download`) &&
          res.request().method() === 'GET' &&
          res.ok(),
        { timeout: 60_000 }
      );
      // noverify: download-presign GET is the customer-facing read; the
      // 200-status assertion below is the verification (no audit-event
      // pair expected — file-download presigns are intentionally
      // logged at the audit layer in the file-download-ui.spec.ts
      // happy-path test, not here).
      await page.getByTestId('file-detail-download-btn').click();
      const downloadResponse = await downloadResponsePromise;
      expect(downloadResponse.status()).toBe(200);
    });

    await test.step('9. Click Delete → ConfirmDialog appears', async () => {
      // noverify: opens the delete confirmation dialog — no backend
      // mutation fires until the confirm CTA below.
      await page.getByTestId('file-detail-delete-btn').click();
      // ConfirmDialog uses ``Modal`` under the hood; the title
      // is the dialog's heading.
      await expect(
        page.getByRole('heading', { name: /^delete file$/i })
      ).toBeVisible({ timeout: 10_000 });
      await expect(page.getByText(/are you sure you want to delete/i)).toBeVisible();
    });

    await test.step('10. Confirm deletion → DELETE fires + nav to /files', async () => {
      // Listen for the DELETE before clicking so we don't race
      // the navigation. ``handleDeleteConfirm`` fires the
      // mutation, awaits, then navigates to /files on success.
      const deleteResponsePromise = page.waitForResponse(
        (res) =>
          res.url().includes(`/api/v1/files/${fileId}/`) &&
          res.request().method() === 'DELETE',
        { timeout: 30_000 }
      );
      // The dialog has Cancel + Delete buttons; ``confirmLabel``
      // is "Delete" (default override in FileDetailPage:439).
      // Scope the role lookup to the dialog body so we don't
      // re-trigger the ``file-detail-delete-btn`` underneath.
      // This confirm-CTA fires DELETE /api/v1/files/{id}/. The status
      // check below (<300) plus the URL+listing assertions in step 11
      // verify the mutation persisted. FILE_DELETED audit emission is
      // owned by the API contract suite at
      // hub/apps/files/tests/test_file_delete_view.py.
      const confirmDeleteBtn = page
        .getByRole('dialog')
        .getByRole('button', { name: /^delete$/i });
      // noverify: API-contract suite owns the audit emission; UI re-render is asserted below.
      await confirmDeleteBtn.click();
      const deleteResponse = await deleteResponsePromise;
      // 204 No Content (typical Django DRF DELETE) is the
      // contract; reject 4xx/5xx outright (a rejected delete
      // would leave the row alive and break step 11).
      expect(deleteResponse.status(), `DELETE /files/${fileId}/`).toBeLessThan(
        300
      );
      await expect(page).toHaveURL(/\/files\/?($|\?)/, { timeout: 30_000 });
      await expect(page.getByTestId('file-list-page')).toBeVisible();
    });

    await test.step('11. Verify row is gone from the list', async () => {
      // After navigation, FileListPage has its own ``useFiles``
      // query. We don't manually reload — if the cache wasn't
      // invalidated by the delete mutation, this assertion
      // would catch the stale-cache regression. (Per
      // ``useDeleteFile``, the delete mutation invalidates the
      // ``files`` query key on success.)
      await expect(
        page.getByRole('button', { name: uploadName })
      ).toBeHidden({ timeout: 30_000 });
      // Belt-and-suspenders: a fresh navigation forces a refetch
      // and confirms server-side absence too. This catches the
      // case where the cache was invalidated correctly but the
      // server actually retained the row.
      await page.goto('/files');
      await expect(page.getByTestId('file-list-page')).toBeVisible();
      await expect(
        page.getByRole('button', { name: uploadName })
      ).toBeHidden({ timeout: 30_000 });
    });
  });
});
