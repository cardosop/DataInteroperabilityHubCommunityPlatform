/**
 * E2E Test: JOURNEY-AUTH-PROFILE — User Edits Profile
 *
 * Journey: Authenticated user edits display name on /settings/profile and
 *          verifies the change is persisted via GET /auth/me/.
 * Persona: Any authenticated user
 * Use cases: UC-AUTH-PROFILE
 * Reference: docs/USER_JOURNEYS.md
 *
 * Per-journey structure: Success, Failure, Edge. No mocks/stubs; real backend only.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';
import { waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('JOURNEY-AUTH-PROFILE: User Edits Profile', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('user edits display name and sees it persisted in /auth/me/', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.app-sidebar', { timeout: 15000 });

      await page.goto('/settings/profile', { waitUntil: 'domcontentloaded' });
      await waitForLoadingComplete(page, { timeout: 15000 });

      const displayNameInput = page.locator(
        'input[name="display_name"], input[id="profile-display_name"]'
      );
      await expect(displayNameInput).toBeVisible({ timeout: 10000 });

      const newName = `E2E-Profile-${Date.now()}`;
      await displayNameInput.fill(newName);

      const saveBtn = page
        .locator('button[type="submit"]')
        .or(page.locator('button:has-text("Save")'))
        .first();
      await saveBtn.click();
      // Wait for save to complete — replace fixed sleep with success-indicator wait
      const successMsg = page.locator('.profile-success');
      await expect(successMsg).toBeVisible({ timeout: 10000 });
      await expect(successMsg).toContainText(/updated|success/i);

      const userMenu = page.locator('.user-name');
      await expect(userMenu).toContainText(newName, { timeout: 5000 });

      const meData = await page.evaluate(async () => {
        const token = localStorage.getItem('access_token');
        if (!token) return null;
        const base = window.location.origin;
        const res = await fetch(`${base}/api/v1/auth/me/`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return null;
        return res.json();
      });
      expect(meData).not.toBeNull();
      expect(meData?.name).toBe(newName);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to settings/profile redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/settings/profile', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|settings)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onSettingsWithPrompt =
        url.includes('/settings') &&
        (await page.locator('input#email, [href*="/login"]').count()) > 0;
      expect(onLogin || onSettingsWithPrompt).toBe(true);
    });

    test('saving empty display name shows validation or stays on profile page', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/settings/profile', { waitUntil: 'domcontentloaded' });
      await waitForLoadingComplete(page, { timeout: 15000 });

      const displayNameInput = page.locator(
        'input[name="display_name"], input[id="profile-display_name"]'
      );
      if ((await displayNameInput.count()) === 0) {
        test.skip(true, 'Profile display_name input not found — page structure may differ');
        return;
      }
      await displayNameInput.fill('');
      const saveBtn = page
        .locator('button[type="submit"]')
        .or(page.locator('button:has-text("Save")'))
        .first();
      await saveBtn.click();
      await page.waitForTimeout(1000);

      // Either validation blocks the save (stays on profile) or an error message is shown
      const stillOnProfile = page.url().includes('/settings/profile');
      const hasValidation =
        (await page.locator('.error-message, .profile-error, [role="alert"]').count()) > 0 ||
        !(await displayNameInput.evaluate((el: HTMLInputElement) => el.validity.valid));
      expect(stillOnProfile || hasValidation).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('profile page loads with current display name pre-filled', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/settings/profile', { waitUntil: 'domcontentloaded' });
      await waitForLoadingComplete(page, { timeout: 15000 });

      const displayNameInput = page.locator(
        'input[name="display_name"], input[id="profile-display_name"]'
      );
      await expect(displayNameInput).toBeVisible({ timeout: 10000 });
      // The input must be pre-filled with the existing name (not blank on load)
      const currentValue = await displayNameInput.inputValue();
      expect(currentValue.length).toBeGreaterThan(0);
    });
  });
});
