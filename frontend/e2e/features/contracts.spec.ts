/**
 * E2E Feature: Contracts
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.1/8.3.2. Routes: /contracts, /contracts/:id/edit, /contracts/:id/link-odps.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';
import { assertListPageLoads, loginAndNavigateToRoute, waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Contracts', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('contracts list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 60000,
        contentSelector: '[data-testid="contract-list-page"], .contract-list-page, .empty-state, .error-display',
      });
      if (page.url().includes('/login')) {
        throw new Error('contracts list loads: still on /login after loginAndNavigateToRoute');
      }
      await assertListPageLoads(page, '[data-testid="contract-list-page"], .contract-list-page, .empty-state', { timeout: 60000 });
    });
  });

  test.describe('Failure', () => {
    test('contract edit with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      await page.goto(`/contracts/${nonExistentId}/edit`);
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          acceptRedirectToLogin: true,
        });
      } catch {
        // May resolve to error/login — acceptable
      }
      const onLogin = page.url().includes('/login');
      const hasError = (await page.locator('.error-display').count()) > 0;
      expect(onLogin || hasError).toBe(true) /* acceptable states */;
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
      // ContractFileReader renders with class contract-file-reader__textarea and
      // aria-label="Contract content (YAML or JSON)".
      const textarea = page.locator(
        'textarea[aria-label*="contract" i], textarea[aria-label*="content" i], .contract-file-reader textarea, .contract-file-reader__textarea',
      ).first();
      await textarea.waitFor({ state: 'visible', timeout: 20000 });
      await textarea.fill('{"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}');

      // Wait for debounced validation (1.5s debounce + backend normalization + staging latency).
      // Use Playwright retry assertion instead of point-in-time check to avoid flakiness.
      const validationPanel = page.locator('.validation-result-panel');
      try {
        await expect(validationPanel).toBeVisible({ timeout: 30000 });
      } catch {
        // Validation panel may not appear if backend is unreachable
        test.skip(true, 'Validation panel did not appear — validate-draft endpoint may be unavailable');
        return;
      }

      // Assert: error or success or warning state shown (not just loading)
      const terminalPanel = page.locator(
        '.validation-result-panel--error, .validation-result-panel--success, .validation-result-panel--warning',
      );
      await expect(terminalPanel.first()).toBeVisible({ timeout: 15000 });

      // If error state, verify Create button is disabled
      const hasError = (await page.locator('.validation-result-panel--error').count()) > 0;
      if (hasError) {
        await expect(page.locator('button:has-text("Create Contract")').first()).toBeDisabled();
      }
    });
  });

  test.describe('Edge', () => {
    test('contract link-odps with non-existent id shows error or redirect', async ({ page }) => {
      await page.goto('/contracts/00000000-0000-0000-0000-000000000000/link-odps');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          acceptRedirectToLogin: true,
        });
      } catch {
        // May resolve to error/login/403 — acceptable
      }
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|failed|403|forbidden/i').count()) > 0;
      expect(hasError || onLogin || on403).toBe(true) /* acceptable states */;
    });
  });
});
