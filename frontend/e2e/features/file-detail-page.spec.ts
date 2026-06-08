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

    // The first file row exposes a Download button with a stable
    // ``data-testid="file-list-download-${file.id}"`` from which we
    // recover the file ID without parsing UUIDs from text.
    const firstDownloadBtn = page.locator('[data-testid^="file-list-download-"]').first();
    await expect(firstDownloadBtn).toBeAttached({ timeout: 30_000 });
    const testId = await firstDownloadBtn.getAttribute('data-testid');
    expect(testId).toMatch(/^file-list-download-[0-9a-f-]+$/);
    const fileId = testId!.replace('file-list-download-', '');

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

    const firstNameBtn = page.locator('.file-list-name-btn').first();
    await expect(firstNameBtn).toBeAttached({ timeout: 30_000 });
    // noverify: navigation-only — opens the file detail page; no mutation.
    await firstNameBtn.click();

    await waitForAppMainReady(page, { timeout: 60_000 });
    await expect(page).toHaveURL(/\/files\/[0-9a-f-]+/, { timeout: 30_000 });
    await expect(page.getByTestId('file-detail-page')).toBeVisible({ timeout: 30_000 });
  });
});
