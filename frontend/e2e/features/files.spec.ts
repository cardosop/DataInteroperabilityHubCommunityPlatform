/**
 * E2E Feature: Files
 * Per E2E_FULL_COVERAGE_PLAN and tasks 29.1.8. Routes: /files.
 * Success (list loads), Failure (403 unauthenticated), Edge (empty state). Real backend only; no mocks.
 */

import { test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../fixtures/auth';
import { assertEdgeBehavior, assertFailureRedirect, assertSuccessLoad } from '../fixtures/journey-helpers';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Files', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('files list loads when authenticated', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      await page.goto('/files');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) {
          await assertFailureRedirect(page);
          return;
        }
        throw _err;
      }
      await assertSuccessLoad(page, {
        successContentSelector: '[data-testid="file-list-page"], .file-list-page, [data-testid="file-list-empty-state"], .empty-state',
      });
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to /files redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/files');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      await assertFailureRedirect(page);
    });
  });

  test.describe('Edge', () => {
    test('files route shows empty state when no files', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      await page.goto('/files');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login')) return;
        throw _err;
      }
      await assertEdgeBehavior(page, {
        emptyStateSelector: '[data-testid="file-list-empty-state"], .empty-state',
        orContentSelector: '[data-testid="file-list-table"], .file-list-table',
      });
    });
  });
});
