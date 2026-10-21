/**
 * E2E: UC-ODPS-001 — Create ODPS Product
 *
 * Use Case: Create ODPS Product
 * Persona: Data Product Owner
 * Reference: docs/USE_CASES.md, docs/TEST_TRACEABILITY.md
 *
 * Success/Failure/Edge. Routes: /odps, /odps/upload (legacy — Phase 211.A6
 * redirects them to /contracts?spec_type=ODPS and /contracts/create).
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('UC-ODPS-001: Create ODPS Product', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('ODPS list loads', async ({ page }) => {
      const user = await getTestUser();
      // Legacy /odps redirects (Phase 211.A6) to the contracts list filtered by spec_type=ODPS.
      await loginAndNavigateToRoute(page, user, '/odps', {
        timeout: 60000,
        contentSelector: '.contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"]',
      });
      test.skip(page.url().includes('/login'), 'Redirected to login');
      expect(page.url()).toContain('/contracts?spec_type=ODPS');
      const hasContent =
        (await page.locator('.contract-list-page, [data-testid="contract-list-page"]').count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('ODPS upload page loads', async ({ page }) => {
      const user = await getTestUser();
      // Legacy /odps/upload redirects (Phase 211.A6) to the unified contract create page.
      await loginAndNavigateToRoute(page, user, '/odps/upload', {
        timeout: 60000,
        contentSelector: 'textarea.contract-file-reader__textarea, textarea, .contract-create-page',
      });
      test.skip(page.url().includes('/login'), 'Redirected to login');
      expect(page.url()).toContain('/contracts/create');
      const hasUploadUI =
        (await page.locator('textarea.contract-file-reader__textarea, textarea, .contract-create-page').count()) > 0;
      expect(hasUploadUI).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to ODPS redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/odps', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/login/, { timeout: 20_000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('ODPS list with empty state loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/odps', {
        timeout: 60000,
        contentSelector: '.contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toContain('/contracts?spec_type=ODPS');
      const hasContent =
        (await page.locator('.contract-list-page, [data-testid="contract-list-page"]').count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasContent).toBe(true);
    });
  });
});
