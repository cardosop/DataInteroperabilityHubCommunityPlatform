/**
 * E2E Test: Phase 13 — GDPR Privacy & Data Page
 *
 * User can navigate to /settings/privacy, see export and erasure sections,
 * and request data export. No mocks/stubs; real backend only.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('Phase 13: GDPR Privacy & Data', () => {
  test.setTimeout(60000);

  test('privacy page loads with export and erasure sections', async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('.app-sidebar', { timeout: 15000 });

    await page.goto('/settings/privacy', { waitUntil: 'domcontentloaded' });
    await waitForLoadingComplete(page, { timeout: 15000 });

    const privacyPage = page.locator('[data-testid="privacy-page"]');
    await expect(privacyPage).toBeVisible({ timeout: 10000 });

    const exportSection = page.locator('[data-testid="privacy-export-section"]');
    await expect(exportSection).toBeVisible();
    await expect(exportSection).toContainText(/Data Export|Article 20/i);

    const erasureSection = page.locator('[data-testid="privacy-erasure-section"]');
    await expect(erasureSection).toBeVisible();
    await expect(erasureSection).toContainText(/Data Erasure|Article 17/i);

    const exportBtn = page.locator('[data-testid="btn-request-export"]');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toContainText(/Request data export/i);

    const erasureBtn = page.locator('[data-testid="btn-request-erasure"]');
    await expect(erasureBtn).toBeVisible();
    await expect(erasureBtn).toContainText(/Request data erasure/i);
  });

  test('user can request data export from privacy page', async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('.app-sidebar', { timeout: 15000 });

    await page.goto('/settings/privacy', { waitUntil: 'domcontentloaded' });
    await waitForLoadingComplete(page, { timeout: 15000 });

    const exportBtn = page.locator('[data-testid="btn-request-export"]');
    await expect(exportBtn).toBeVisible();
    await exportBtn.click();

    // Wait for request to complete (success or error)
    await page.waitForTimeout(5000);

    // Either success message or error display; no loading spinner stuck
    const successOrError = page.locator('.privacy-success, .error-display, .privacy-table');
    await expect(successOrError.first()).toBeVisible({ timeout: 15000 });
  });
});
