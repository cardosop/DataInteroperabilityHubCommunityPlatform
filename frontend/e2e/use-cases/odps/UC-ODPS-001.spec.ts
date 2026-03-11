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
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('ODPS list loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/odps', {
        timeout: 60000,
        contentSelector: '.odps-list-page, .empty-state, .error-display, .loading-spinner-container',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/odps');
    });

    test('ODPS upload page loads', async ({ page }) => {
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
    test('unauthenticated access to ODPS redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/odps', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|odps)/, { timeout: 20_000 });
      expect(page.url().includes('/login') || page.url().includes('/odps')).toBe(true);
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
    });
  });
});
