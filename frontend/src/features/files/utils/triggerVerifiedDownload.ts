/**
 * Phase 260.3.G UI integration — wire :func:`downloadFileWithVerification`
 * to a browser-native save-as flow.
 *
 * On a verified (or skipped) download we:
 *   1. fetch + verify via :func:`downloadFileWithVerification`,
 *   2. create an in-memory Blob URL,
 *   3. trigger a click on an off-DOM ``<a download>`` element so the
 *      browser shows the user the save-as dialog,
 *   4. revoke the Blob URL after the click to free memory.
 *
 * On a mismatch the wrapper rethrows :class:`ChecksumMismatchError`
 * so callers (FileListPage / FileDetailModal) can surface a toast
 * AND the platform audit row is already durable.
 */

import {
  downloadFileWithVerification,
  type DownloadFileResult,
  type S3FetchFn,
} from './downloadFileWithVerification';

interface Options {
  /** Injectable for testability; defaults to the real fetch transport. */
  s3Fetch?: S3FetchFn;
  /**
   * Phase 260.3.G.R1 GAP-B — pass the catalog ``size`` so the
   * orchestrator can pre-flight the in-browser verification cap and
   * throw :class:`FileTooLargeForVerificationError` BEFORE allocating
   * a multi-GiB Blob. The FileListPage catches that and falls back
   * to the legacy presign-and-navigate flow.
   */
  fileSizeBytes?: number;
}

export async function triggerVerifiedDownload(
  fileId: string,
  options: Options = {}
): Promise<DownloadFileResult> {
  const result = await downloadFileWithVerification(fileId, options);

  // Off-DOM anchor + programmatic click is the standard cross-browser
  // recipe for "save this Blob to disk with a custom filename"
  // — equivalent to what file-saver does.
  const objectUrl = URL.createObjectURL(result.blob);
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = result.filename || 'download';
  // Append + click + remove. Don't keep the anchor in the DOM.
  document.body.appendChild(anchor);
  try {
    anchor.click();
  } finally {
    document.body.removeChild(anchor);
    URL.revokeObjectURL(objectUrl);
  }

  return result;
}
