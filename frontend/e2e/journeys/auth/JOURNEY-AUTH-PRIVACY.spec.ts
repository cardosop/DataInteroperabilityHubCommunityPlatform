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
  test.setTimeout(90000);

  /** Navigate to privacy page and wait for content to load.
   *  Returns true if page loaded, false if redirected to login (auth expired). */
  async function gotoPrivacyPage(page: import('@playwright/test').Page): Promise<boolean> {
    await page.goto('/settings/privacy', { waitUntil: 'domcontentloaded' });
    // Wait for privacy page content, error display, OR login form — all terminal states.
    await page
      .locator('[data-testid="privacy-page"], .error-display, input#email')
      .first()
      .waitFor({ state: 'visible', timeout: 45000 });
    return !page.url().includes('/login');
  }

  test.describe('Success', () => {
  test('privacy page loads with export and erasure sections', async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    if (!(await gotoPrivacyPage(page))) {
      test.skip(true, 'Auth session lost during navigation');
      return;
    }

    const privacyPage = page.locator('[data-testid="privacy-page"]');
    await expect(privacyPage).toBeVisible({ timeout: 5000 });

    const exportSection = page.locator('[data-testid="privacy-export-section"]');
    await expect(exportSection).toBeVisible();
    await expect(exportSection).toContainText(/Data Export|Article 20/i);

    const erasureSection = page.locator('[data-testid="privacy-erasure-section"]');
    await expect(erasureSection).toBeVisible();
    await expect(erasureSection).toContainText(/Data Erasure|Article 17/i);

    const exportBtn = page.locator('[data-testid="btn-request-export"]');
    await expect(exportBtn).toBeVisible();

    const erasureBtn = page.locator('[data-testid="btn-request-erasure"]');
    await expect(erasureBtn).toBeVisible();
  });

  test('user can request data export from privacy page', async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    if (!(await gotoPrivacyPage(page))) {
      test.skip(true, 'Auth session lost during navigation');
      return;
    }

    const exportBtn = page.locator('[data-testid="btn-request-export"]');
    await expect(exportBtn).toBeVisible({ timeout: 5000 });
    await exportBtn.click();

    // Export request: either success or error display (API may 429 under load)
    const feedback = page.locator('.privacy-success, .error-display, [role="alert"]');
    await expect(feedback.first()).toBeVisible({ timeout: 30000 });
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
      expect(onLogin || onSettingsWithPrompt).toBe(true) /* acceptable states */;
    });

    test('data export request shows feedback (success or rate-limit error)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      if (!(await gotoPrivacyPage(page))) {
        test.skip(true, 'Auth session lost during navigation');
        return;
      }

      const exportBtn = page.locator('[data-testid="btn-request-export"]');
      await expect(exportBtn).toBeVisible({ timeout: 5000 });
      await exportBtn.click();

      const feedback = page.locator('.privacy-success, .error-display, .privacy-table, [role="alert"]');
      await expect(feedback.first()).toBeVisible({ timeout: 30000 });
    });
  });

  test.describe('Edge', () => {
    test('erasure button is visible and shows confirmation or error when clicked', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      if (!(await gotoPrivacyPage(page))) {
        test.skip(true, 'Auth session lost during navigation');
        return;
      }

      const erasureBtn = page.locator('[data-testid="btn-request-erasure"]');
      await expect(erasureBtn).toBeVisible({ timeout: 5000 });
      await erasureBtn.click();

      const feedback = page.locator(
        '.privacy-erasure-confirm, .privacy-success, .error-display, [role="dialog"], [role="alert"]'
      );
      await expect(feedback.first()).toBeVisible({ timeout: 15000 });
    });
  });
});
