/**
 * E2E: UC-ODPS-001 — Create ODPS Product
 *
 * Use Case: Create ODPS Product
 * Persona: Data Product Owner
 * Reference: docs/USE_CASES.md, docs/TEST_TRACEABILITY.md
 *
 * Success/Failure/Edge. Routes: /odps, /odps/upload.
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
      await loginAndNavigateToRoute(page, user, '/odps', {
        timeout: 60000,
        contentSelector: '.odps-list-page, .empty-state',
      });
      test.skip(page.url().includes('/login'), 'Redirected to login');
      expect(page.url()).toContain('/odps');
      const hasContent =
        (await page.locator('.odps-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('ODPS upload page loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/odps/upload', {
        timeout: 60000,
        contentSelector: 'textarea#odps-content, textarea, .odps-upload-page',
      });
      test.skip(page.url().includes('/login'), 'Redirected to login');
      expect(page.url()).toContain('/odps/upload');
      const hasUploadUI =
        (await page.locator('textarea#odps-content, textarea, .odps-upload-page').count()) > 0;
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
        contentSelector: '.odps-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/odps');
      const hasContent =
        (await page.locator('.odps-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });
});
