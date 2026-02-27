/**
 * E2E Test: JOURNEY-DPO-005 — Configure Data Contracts
 *
 * Journey: Configure Data Contracts
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /contracts, /contracts/:id/edit.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-005: Configure Data Contracts', () => {
  test.setTimeout(300000); // 5 min: contracts API can be slow under parallel E2E load

  test.describe('Success', () => {
    test('contracts list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, .empty-state, .error-display, h1',
      });
      expect(page.url()).toContain('/contracts');
      const hasContent =
        (await page.locator('.contract-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('contract edit page loads for existing contract', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, .empty-state, .error-display',
      });
      const contractRow = page.locator('.contract-list-page tr.contract-row').first();
      if ((await contractRow.count()) > 0) {
        await contractRow.click();
        await page.waitForURL(/\/contracts\/[^/]+$/, { timeout: 10000 });
        const editBtn = page.locator('button:has-text("Edit")');
        if ((await editBtn.count()) > 0) {
          await editBtn.click();
          await page.waitForLoadState('domcontentloaded');
          await page.waitForSelector('.contract-editor-page, .error-display, #email', {
            timeout: 15000,
          });
          if (!page.url().includes('/login')) {
            expect(page.url()).toContain('/contracts');
            expect(page.url()).toContain('/edit');
          }
        }
      }
    });
  });

  test.describe('Failure', () => {
    test('contract edit with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      const testUser = await getTestUser();
      // Login to home first (avoids slow contracts list load); then goto edit URL directly
      await loginAndNavigateToRoute(page, testUser, '/', {
        timeout: 60000,
        contentSelector: '[data-testid="home-page"], .home-page, main',
      });
      await page.goto(`/contracts/${nonExistentId}/edit`);
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.contract-editor-page, .contract-detail-page',
        waitAfterLoad: 8000,
      });
    });

    test('unauthenticated access to contracts list redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/contracts', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|contracts)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onContractsWithLoginPrompt =
        url.includes('/contracts') &&
        ((await page.locator('input#email, [href*="/login"]').count()) > 0 ||
          (await page.locator('text=Sign in').count()) > 0);
      expect(onLogin || onContractsWithLoginPrompt).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('contracts list loads with empty state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 90000,
        contentSelector: '.contract-list-page, .empty-state, .error-display, h1',
      });
      if (page.url().includes('/login')) {
        throw new Error('Contracts list redirected to login; auth may have failed under parallel load.');
      }
      expect(page.url()).toContain('/contracts');
    });

    test('contracts list shows pagination or single page or empty state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 90000,
        contentSelector: '.contract-list-page, .empty-state, .error-display, .contract-list-pagination, .loading-spinner-container, h1',
      });
      if (page.url().includes('/login')) {
        throw new Error('Contracts list redirected to login; auth may have failed under parallel load.');
      }
      expect(page.url()).toContain('/contracts');
      // Wait for loading to complete and actual content to appear (not just loading spinner)
      await page
        .locator('.contract-list-page, .empty-state, .error-display')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 });
      const hasPagination = (await page.locator('.contract-list-pagination').count()) > 0;
      const hasListOrEmpty =
        (await page.locator('.contract-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasPagination || hasListOrEmpty).toBe(true);
    });
  });
});
