/**
 * After `GET /files/{id}/download/` returns a presigned object-store URL, send the
 * browser there to fetch the bytes.
 *
 * Opening a **new** top-level browsing context (`window.open`) keeps the Meshant SPA
 * loaded so users stay on the file list (and Playwright can continue the journey).
 * When pop-ups are blocked or `window.open` is unavailable, fall back to same-tab
 * `location.assign` (spec/task wording: navigation to the presigned URL).
 */
export function openPresignedDownloadUrl(url: string): void {
  const opened = window.open(url, '_blank', 'noopener,noreferrer');
  if (opened == null) {
    window.location.assign(url);
    return;
  }
  try {
    if (opened.closed) {
      window.location.assign(url);
    }
  } catch {
    window.location.assign(url);
  }
}
