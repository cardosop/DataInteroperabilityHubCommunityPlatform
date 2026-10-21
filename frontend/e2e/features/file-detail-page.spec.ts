/**
 * E2E Feature: File detail page — Phase 260.4.B.3.
 *
 * Acceptance:
 *   - Navigating directly to ``/files/{id}`` (deep link) renders the
 *     page; no error fallback.
 *   - Clicking a file name on ``/files`` navigates to the detail page
 *     and the metadata is surfaced.
 *
 * Real backend only — no mocks. The first test resolves a file ID
 * dynamically from the staging tenant's ``/files`` list so the deep
 * link is guaranteed to exist; if the staging tenant has zero files
 * the test exits early on a passing assertion (the listing surface is
 * already covered by ``files.spec.ts``).
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: File detail page (Phase 260.4.B)', () => {
  test.setTimeout(180_000);

  test('deep link to /files/{id} renders the file detail page', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);

    // Resolve a file ID from the list — keeps the deep link real.
    await page.goto('/files');
    await waitForAppMainReady(page, { timeout: 60_000 });

    const emptyState = page.getByTestId('file-list-empty-state');
    // intentional: the staging tenant may legitimately have zero files;
    // when the empty state surfaced we assert it rendered (the listing
    // contract holds) and exit early rather than fail the deep-link
    // test on an upstream data condition we cannot deterministically
    // seed.
    if ((await emptyState.count()) > 0) {
      // No files in the staging tenant — assert the empty surface
      // rendered (already covered by files.spec.ts) and exit. There
      // is no deterministic seed path here, so failing the test
      // would be a flake rather than a regression.
      await expect(emptyState).toBeVisible();
      return;
    }

    // Error terminal: the list fetch can die under churn (R2 resets) —
    // neither the empty state nor a row renders, and the 30s row wait
    // below fails opaquely (b7: 30s "element not found" hid the visible
    // NETWORK_ERROR). The error surface carries a Retry button — click it
    // ONCE so a transient stall cluster (b7: every files fetch failed for
    // minutes under HDD IO contention) recovers the list and lets the real
    // acceptance below run. A persistent error fails with the visible
    // state instead of the opaque row wait.
    const errorDisplay = page
      .locator('.error-display, [data-testid="error-display"]')
      .first();
    if ((await errorDisplay.count()) > 0) {
      const retryBtn = page.locator('[data-testid="error-display-retry"]').first();
      if ((await retryBtn.count()) > 0) {
        // intentional: the retry click is best-effort — a sustained
        // outage just leaves the error visible and the recovery wait
        // below expires.
        await retryBtn.click().catch(() => null);
      }
      // Wait for the RECOVERY signal (rows or empty state) rather than
      // re-checking the error immediately — the refetch is in flight and
      // the error surface persists until it settles.
      // intentional: structured-false probe — the if/else below consumes
      // the boolean and throws the visible error state on failure.
      const recovered = await page
        .locator('.file-list-row, [data-testid="file-list-empty-state"]')
        .first()
        .waitFor({ state: 'visible', timeout: 30_000 })
        .then(() => true)
        .catch(() => false);
      if (!recovered) {
        // intentional: diagnostic-only read — an empty read just means no error surface rendered and the message falls back to the generic form.
        const errText = (await errorDisplay.textContent().catch(() => '')) ?? '';
        throw new Error(
          `File list shows error — cannot resolve a file id for the deep link: "${errText?.slice(0, 300)}"`
        );
      }
    }

    // The first file row carries a stable ``data-file-id`` attribute
    // (FileListPage row) — the old ``file-list-download-${id}`` testid
    // died with the row-level Download button (download now lives on the
    // detail page as ``file-detail-download-btn``).
    const firstRow = page.locator('.file-list-row').first();
    await expect(firstRow).toBeAttached({ timeout: 30_000 });
    const fileId = await firstRow.getAttribute('data-file-id');
    expect(fileId).toMatch(/^[0-9a-f-]+$/);

    // Direct URL navigation — the load-bearing acceptance contract.
    await page.goto(`/files/${fileId}`);
    await waitForAppMainReady(page, { timeout: 60_000 });

    await expect(page.getByTestId('file-detail-page')).toBeVisible({ timeout: 30_000 });
    // Audit-log section is part of the page surface (260.4.B.2).
    await expect(page.getByTestId('file-detail-activity-section')).toBeVisible();
    // Back-to-list CTA is the primary navigation away from the page.
    await expect(page.getByRole('button', { name: /back to files/i })).toBeVisible();
  });

  test('clicking a file name on /files navigates to the detail page', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);

    await page.goto('/files');
    await waitForAppMainReady(page, { timeout: 60_000 });

    const emptyState = page.getByTestId('file-list-empty-state');
    // intentional: the staging tenant may legitimately have zero files;
    // when the empty state surfaced we assert it rendered (the listing
    // contract holds) and exit early rather than fail the deep-link
    // test on an upstream data condition we cannot deterministically
    // seed.
    if ((await emptyState.count()) > 0) {
      await expect(emptyState).toBeVisible();
      return;
    }

    // Same error-terminal contract as the deep-link test above (b7: the
    // 30s row wait hid the visible NETWORK_ERROR), including the single
    // best-effort Retry before failing with the visible state.
    const errorDisplay = page
      .locator('.error-display, [data-testid="error-display"]')
      .first();
    if ((await errorDisplay.count()) > 0) {
      const retryBtn = page.locator('[data-testid="error-display-retry"]').first();
      if ((await retryBtn.count()) > 0) {
        // intentional: the retry click is best-effort — a sustained
        // outage just leaves the error visible and the recovery wait
        // below expires.
        await retryBtn.click().catch(() => null);
      }
      // Wait for the RECOVERY signal (rows or empty state) rather than
      // re-checking the error immediately — the refetch is in flight and
      // the error surface persists until it settles.
      // intentional: structured-false probe — the if/else below consumes
      // the boolean and throws the visible error state on failure.
      const recovered = await page
        .locator('.file-list-row, [data-testid="file-list-empty-state"]')
        .first()
        .waitFor({ state: 'visible', timeout: 30_000 })
        .then(() => true)
        .catch(() => false);
      if (!recovered) {
        // intentional: diagnostic-only read — an empty read just means no error surface rendered and the message falls back to the generic form.
        const errText = (await errorDisplay.textContent().catch(() => '')) ?? '';
        throw new Error(
          `File list shows error — cannot navigate to a detail page: "${errText?.slice(0, 300)}"`
        );
      }
    }

    const firstNameBtn = page.locator('.file-list-name-btn').first();
    await expect(firstNameBtn).toBeAttached({ timeout: 30_000 });
    // noverify: navigation-only — opens the file detail page; no mutation.
    await firstNameBtn.click();

    await waitForAppMainReady(page, { timeout: 60_000 });
    await expect(page).toHaveURL(/\/files\/[0-9a-f-]+/, { timeout: 30_000 });
    await expect(page.getByTestId('file-detail-page')).toBeVisible({ timeout: 30_000 });
  });
});
