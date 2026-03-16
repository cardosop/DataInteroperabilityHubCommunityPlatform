/**
 * E2E Test: JOURNEY-AUTH-PRIVACY — GDPR Privacy & Data Page
 *
 * Journey: Authenticated user views /settings/privacy, sees GDPR export and erasure
 *          sections, and can request a data export.
 * Persona: Any authenticated user
 * Use cases: GDPR Article 17 / Article 20
 * Reference: docs/USER_JOURNEYS.md
 *
 * Per-journey structure: Success, Failure, Edge. No mocks/stubs; real backend only.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';
import { waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('JOURNEY-AUTH-PRIVACY: GDPR Privacy & Data', () => {
  test.setTimeout(60000);

  test.describe('Success', () => {
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

    // Export request must succeed — not error
    await expect(page.locator('.privacy-success')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('.error-display')).not.toBeVisible();
  });
  }); // end Success

  test.describe('Failure', () => {
    test('unauthenticated access to settings/privacy redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/settings/privacy', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|settings)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onSettingsWithPrompt =
        url.includes('/settings') &&
        (await page.locator('input#email, [href*="/login"]').count()) > 0;
      expect(onLogin || onSettingsWithPrompt).toBe(true);
    });

    test('data export request shows feedback (success or rate-limit error)', async ({ page }) => {
      // Verifies that clicking Request Export does not silently fail (no blank/stuck state).
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/settings/privacy', { waitUntil: 'domcontentloaded' });
      await waitForLoadingComplete(page, { timeout: 15000 });

      const exportBtn = page.locator('[data-testid="btn-request-export"]');
      await expect(exportBtn).toBeVisible({ timeout: 10000 });
      await exportBtn.click();

      // Either success or error feedback must appear within 15s — a stuck spinner is a failure
      const feedback = page.locator('.privacy-success, .error-display, .privacy-table, [role="alert"]');
      await expect(feedback.first()).toBeVisible({ timeout: 15000 });
    });
  });

  test.describe('Edge', () => {
    test('erasure button is visible and shows confirmation or error when clicked', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/settings/privacy', { waitUntil: 'domcontentloaded' });
      await waitForLoadingComplete(page, { timeout: 15000 });

      const erasureBtn = page.locator('[data-testid="btn-request-erasure"]');
      await expect(erasureBtn).toBeVisible({ timeout: 10000 });
      await expect(erasureBtn).toContainText(/Request data erasure/i);
      await erasureBtn.click();

      // After clicking erasure, the UI must react — confirmation dialog, error, or pending state
      const feedback = page.locator(
        '.privacy-erasure-confirm, .privacy-success, .error-display, [role="dialog"], [role="alert"]'
      );
      await expect(feedback.first()).toBeVisible({ timeout: 10000 });
    });
  });
});
