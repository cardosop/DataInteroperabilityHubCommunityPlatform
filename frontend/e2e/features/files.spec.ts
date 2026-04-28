/**
 * E2E Feature: Files
 * Per E2E_FULL_COVERAGE_PLAN and tasks 29.1.8. Routes: /files.
 * Success (list loads), Failure (403 unauthenticated), Edge (empty state). Real backend only; no mocks.
 */

import { test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../fixtures/auth';
import { assertEdgeBehavior, assertFailureRedirect, assertSuccessLoad } from '../fixtures/journey-helpers';
import { waitForAppMainReady } from '../fixtures/helpers';

// storageState from chromium-mvp injects auth, but the token can expire
// during long (1.4 h) staging runs. loginUser() fast-paths when storageState
// is still valid (<1 s) and re-authenticates when it's not — eliminating
// the "Redirected to login — session expired" skip that plagued this spec.

test.describe('Feature: Files', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('files list loads when authenticated', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      await page.goto('/files');
      await waitForAppMainReady(page, { timeout: 60000 });
      await assertSuccessLoad(page, {
        successContentSelector: '[data-testid="file-list-page"], .file-list-page, [data-testid="file-list-empty-state"], .empty-state, [data-testid="empty-state"]',
      });
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to /files redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/files');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          acceptRedirectToLogin: true,
        });
      } catch (err) {
        // Only acceptable if we ended up on /login (auth guard triggered)
        if (!page.url().includes('/login')) throw err;
      }
      await assertFailureRedirect(page);
    });
  });

  test.describe('Edge', () => {
    test('files route shows empty state when no files', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      await page.goto('/files');
      await waitForAppMainReady(page, { timeout: 60000 });
      await assertEdgeBehavior(page, {
        emptyStateSelector: '[data-testid="file-list-empty-state"], .empty-state, [data-testid="empty-state"]',
        orContentSelector: '.file-list-table, [data-testid="file-list-table"]',
      });
    });
  });
});
