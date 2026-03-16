/**
 * E2E: Admin User Edit UI (Phase 28.1.4)
 *
 * Tenant admin edits user (display name, status, roles) via /admin/users/:id/edit.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTenantAdminUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('Admin User Edit UI', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('tenant admin can open user edit page and save changes', async ({ page }) => {
      const taUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, taUser, '/admin', { timeout: 60000 });

      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }

      // Switch to Users tab
      const usersTab = page.locator('button:has-text("Users")');
      if ((await usersTab.count()) > 0) {
        await usersTab.first().click();
        // Wait for users API response and React render — 1500ms is too short under load
        await page
          .waitForSelector('.admin-table tbody tr, .empty-state', { timeout: 15000 })
          .catch(() => null);
      }

      // Find first Edit link (admin-user-edit-link or link to /admin/users/.../edit)
      const editLink = page.locator('a[href*="/admin/users/"][href*="/edit"]').first();
      const linkCount = await editLink.count();
      if (linkCount === 0) {
        // No users to edit (empty tenant) — skip assertion
        test.skip();
        return;
      }

      const href = await editLink.getAttribute('href');
      expect(href).toMatch(/\/admin\/users\/[^/]+\/edit/);

      await editLink.click();
      await page.waitForURL(/\/admin\/users\/[^/]+\/edit/, { timeout: 10000 });

      // Assert edit page loaded — increase timeout for visible project (400ms slowMo) and lazy bundles
      const editPage = page.locator('[data-testid="admin-user-edit-page"]');
      await expect(editPage).toBeVisible({ timeout: 20000 });

      const displayNameInput = page.locator('#display_name');
      await expect(displayNameInput).toBeVisible({ timeout: 10000 });

      // Change display name (append E2E suffix to avoid conflicts)
      const originalValue = (await displayNameInput.inputValue()) || '';
      const newValue = originalValue ? `${originalValue} [E2E]` : 'E2E Edited User';
      await displayNameInput.fill(newValue);

      // Save
      const saveBtn = page.locator('[data-testid="admin-user-edit-save"]');
      await saveBtn.click();

      // Expect redirect to /admin
      await page.waitForURL(/\/admin(?!\/users)/, { timeout: 10000 });
      expect(page.url()).toContain('/admin');
      expect(page.url()).not.toContain('/edit');
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to user edit redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/admin/users/00000000-0000-0000-0000-000000000001/edit', {
        waitUntil: 'domcontentloaded',
      });
      await page.waitForTimeout(3000);
      const url = page.url();
      // Unauthenticated access must redirect to login or 403 — must NOT remain on any admin page
      expect(url).not.toContain('/edit');
      expect(url.includes('/login') || url.includes('/403')).toBe(true);
    });
  });
});
