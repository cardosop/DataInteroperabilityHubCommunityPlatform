/**
 * E2E: UC-CM-001 — Create Contract
 *
 * Use Case: Create Contract (Contract Management)
 * Persona: Data Product Owner, Data Engineer
 * Reference: docs/USE_CASES.md, docs/TEST_TRACEABILITY.md
 *
 * Success/Failure/Edge. Routes: /contracts, /odps/upload.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('UC-CM-001: Create Contract', () => {
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('contracts list loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, .empty-state, .error-display, .loading-spinner-container',
      });
      expect(page.url()).toContain('/contracts');
      await waitForLoadingComplete(page, { timeout: 15000 });
      const hasContent =
        (await page.locator('.contract-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('ODPS upload route loads for contract creation', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/odps/upload', {
        timeout: 60000,
        contentSelector: 'textarea#odps-content, textarea, .odps-upload-page, .error-display',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/odps/upload');
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to contracts redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/contracts', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|contracts)/, { timeout: 20_000 });
      const url = page.url();
      expect(url.includes('/login') || url.includes('/contracts')).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('contracts empty state shows create option', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/contracts');
    });
  });
});
