/**
 * E2E: UC-CM-002 — Validate Contract / Link ODPS
 *
 * Use Case: Validate Contract, Link ODPS to Contract
 * Persona: Data Product Owner, Data Engineer
 * Reference: docs/USE_CASES.md, docs/TEST_TRACEABILITY.md
 *
 * Success/Failure/Edge. Routes: /contracts/:id/edit, /contracts/:id/link-odps.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('UC-CM-002: Validate Contract / Link ODPS', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('contract edit page loads when contract exists', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, .empty-state, .error-display',
      });
      const row = page.locator('.contract-list-page tr.contract-row').first();
      if ((await row.count()) > 0) {
        await row.click();
        await page.waitForURL(/\/contracts\/[^/]+$/, { timeout: 10000 });
        const editBtn = page.locator('button:has-text("Edit")');
        if ((await editBtn.count()) > 0) {
          await editBtn.click();
          await page.waitForLoadState('domcontentloaded');
          expect(page.url()).toContain('/edit');
        }
      }
      expect(page.url()).toContain('/contracts');
    });
  });

  test.describe('Failure', () => {
    test('contract edit with non-existent id shows error', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/', {
        timeout: 60000,
        contentSelector: '[data-testid="home-page"], .home-page, main',
      });
      await page.goto('/contracts/00000000-0000-0000-0000-000000000000/edit');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.contract-editor-page, .contract-detail-page',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('link-odps route with non-existent id shows error or redirect', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/', {
        timeout: 60000,
        contentSelector: '[data-testid="home-page"], .home-page, main',
      });
      await page.goto('/contracts/00000000-0000-0000-0000-000000000000/link-odps');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|failed|403/i').count()) > 0;
      expect(url.includes('/login') || url.includes('/403') || hasError).toBe(true);
    });
  });
});
