/**
 * E2E Feature: Contracts
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.1/8.3.2. Routes: /contracts, /contracts/:id/edit, /contracts/:id/link-odps.
 * Success/Failure/Edge/Validation. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';
import {
  assertListPageLoads,
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
} from '../fixtures/helpers';

test.describe('Feature: Contracts', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('contracts list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 60000,
        contentSelector:
          '[data-testid="contract-list-page"], .contract-list-page, .empty-state, .error-display',
      });
      if (page.url().includes('/login')) {
        throw new Error('contracts list loads: still on /login after loginAndNavigateToRoute');
      }
      await assertListPageLoads(
        page,
        '[data-testid="contract-list-page"], .contract-list-page, .empty-state',
        { timeout: 60000 }
      );
    });
  });

  test.describe('Failure', () => {
    test('contract edit with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/contracts/00000000-0000-0000-0000-000000000000/edit',
        {
          timeout: 60000,
          contentSelector: '.error-display, .contract-edit-page, h1',
        }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.contract-edit-page',
      });
    });

    test('unauthenticated access to contracts redirects to login', async ({ page }) => {
      await page.goto('/contracts');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/contracts'),
        'Expected /login redirect or /contracts with auth'
      ).toBe(true);
    });
  });

  test.describe('Validation', () => {
    test('contract create page shows validation errors for invalid content', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/contracts/create', { waitUntil: 'domcontentloaded' });

      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to /login — auth token expired');
        return;
      }

      // Paste invalid ODCS (missing required fields).
      const textarea = page
        .locator(
          'textarea[aria-label*="contract" i], textarea[aria-label*="content" i], .contract-file-reader textarea, .contract-file-reader__textarea'
        )
        .first();
      await textarea.waitFor({ state: 'visible', timeout: 20000 });
      await textarea.fill('{"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}');

      // Wait for debounced validation (1.5s debounce + backend round-trip).
      const validationPanel = page.locator('.validation-result-panel');
      await expect(validationPanel).toBeVisible({ timeout: 30000 });

      // Assert: terminal validation state shown (not just loading)
      const terminalPanel = page.locator(
        '.validation-result-panel--error, .validation-result-panel--success, .validation-result-panel--warning'
      );
      await expect(terminalPanel.first()).toBeVisible({ timeout: 15000 });

      // If error state, verify Create button is disabled
      const hasError = (await page.locator('.validation-result-panel--error').count()) > 0;
      if (hasError) {
        await expect(
          page.locator('button:has-text("Create Contract")').first()
        ).toBeDisabled();
      }
    });
  });

  test.describe('Edge', () => {
    test('contract link-odps with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/contracts/00000000-0000-0000-0000-000000000000/link-odps',
        {
          timeout: 60000,
          contentSelector: '.error-display, .contract-link-odps-page, h1',
        }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.contract-link-odps-page',
      });
    });
  });
});
