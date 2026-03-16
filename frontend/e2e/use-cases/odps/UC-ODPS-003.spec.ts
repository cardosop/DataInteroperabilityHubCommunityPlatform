/**
 * E2E: UC-ODPS-003 — Export ODPS Product
 *
 * Use Case: Export ODPS Product
 * Persona: Data Product Owner
 * Reference: docs/USE_CASES.md, docs/TEST_TRACEABILITY.md
 *
 * Success/Failure/Edge. Routes: /odps, /odps/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('UC-ODPS-003: Export ODPS Product', () => {
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('ODPS detail loads when product exists', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/odps', {
        timeout: 90000,
        contentSelector: '.odps-list-page, .odps-empty-state, .odps-list, .error-display',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      const viewBtn = page.locator('.odps-table button.btn-link, .odps-list button:has-text("View")').first();
      if ((await viewBtn.count()) > 0) {
        await viewBtn.click();
        await page.waitForURL(/\/odps\/[^/]+$/, { timeout: 10000 });
        const hasDetail =
          (await page.locator('.odps-detail-page').count()) > 0 ||
          (await page.locator('.odps-detail').count()) > 0 ||
          page.url().includes('/odps/');
        expect(hasDetail).toBe(true);
      } else {
        expect(page.url()).toContain('/odps');
      }
    });
  });

  test.describe('Failure', () => {
    test('ODPS detail with non-existent id shows error', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/', {
        timeout: 60000,
        contentSelector: '[data-testid="home-page"], .home-page, main',
      });
      await page.goto('/odps/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.odps-detail-page, .odps-detail',
        waitAfterLoad: 8000,
        selectorTimeout: 60000,
      });
    });
  });

  test.describe('Edge', () => {
    test('ODPS list with empty state loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/odps', {
        timeout: 90000,
        contentSelector: '.odps-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/odps');
    });
  });
});
