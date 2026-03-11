/**
 * E2E Test: Phase 7.4 — User Profile Edit
 *
 * User edits profile via /settings/profile and sees changes in /auth/me/.
 * No mocks/stubs; real backend only.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('Phase 7.4: User Profile Edit', () => {
  test.setTimeout(120000);

  test('user edits profile and sees changes in /auth/me/', async ({ page }) => {
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
    await page.waitForTimeout(2000);

    const successMsg = page.locator('.profile-success');
    await expect(successMsg).toBeVisible({ timeout: 5000 });
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
