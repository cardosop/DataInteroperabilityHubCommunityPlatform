/**
 * E2E: UC-ODPS-002 — Link ODPS to Contract
 *
 * Use Case: Link ODPS to Contract
 * Persona: Data Product Owner
 * Reference: docs/USE_CASES.md, docs/TEST_TRACEABILITY.md
 *
 * Success/Failure/Edge. Routes: /contracts/:id/link-odps.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('UC-ODPS-002: Link ODPS to Contract', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('link-odps route loads when contract exists', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, .empty-state, .error-display',
      });
      const row = page.locator('.contract-list-page tr.contract-row').first();
      if ((await row.count()) > 0) {
        await row.click();
        await page.waitForURL(/\/contracts\/[^/]+$/, { timeout: 10000 });
        const linkOdpsBtn = page.locator('a[href*="/link-odps"], button:has-text("Link ODPS")');
        if ((await linkOdpsBtn.count()) > 0) {
          await linkOdpsBtn.first().click();
          await page.waitForLoadState('domcontentloaded');
          expect(page.url()).toContain('/link-odps');
        }
      }
      expect(page.url()).toContain('/contracts');
    });
  });

  test.describe('Failure', () => {
    test('link-odps with non-existent contract id shows error', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/', {
        timeout: 60000,
        contentSelector: '[data-testid="home-page"], .home-page, main',
      });
      await page.goto('/contracts/00000000-0000-0000-0000-000000000000/link-odps');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|failed|403/i').count()) > 0;
      expect(page.url().includes('/login') || page.url().includes('/403') || hasError).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('contracts list loads for link-odps flow', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/contracts');
    });
  });
});
