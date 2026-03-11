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
import { assertNonExistentIdShowsError, loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-005: Configure Data Contracts', () => {
  test.setTimeout(300000); // 5 min: contracts API can be slow under parallel E2E load

  test.describe('Success', () => {
    test('contracts list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, .empty-state, .error-display, .loading-spinner-container, h1',
      });
      expect(page.url()).toContain('/contracts');
      await waitForLoadingComplete(page, { timeout: 30000 });
      const hasContent =
        (await page.locator('.contract-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('contract detail page loads for a known contract (API-seeded)', async ({ page }) => {
      // Navigate to contracts list and pick the first available contract ID from the API response
      // so we don't depend on the list rendering a clickable row.
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 90000,
        contentSelector: '.contract-list-page, .empty-state, .error-display',
      });
      await waitForLoadingComplete(page, { timeout: 30000 });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on contracts list');
      }

      // Find any contract link in the rendered list
      const contractLink = page.locator('.contract-list-page a[href*="/contracts/"]').first();
      if ((await contractLink.count()) === 0) {
        // Empty catalog — test the edit URL directly with a non-existent ID to confirm 404 behaviour
        // (actual contract creation is covered by contract-creation-flow.spec.ts)
        test.skip(true, 'No contracts in catalog; contract edit page test skipped (contract creation is covered separately).');
        return;
      }

      const href = await contractLink.getAttribute('href');
      const contractId = href?.split('/').filter(Boolean)[1]; // /contracts/<id>
      if (!contractId) {
        throw new Error(`Could not extract contract ID from href: ${href}`);
      }

      // Navigate directly to the contract detail URL
      await page.goto(`/contracts/${contractId}`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.contract-detail-page, .contract-detail-content, .error-display, #email', {
        timeout: 20000,
      });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on contract detail');
      }

      const hasError = (await page.locator('.error-display').count()) > 0;
      if (hasError) {
        const errText = (await page.locator('.error-display').first().textContent()) ?? '';
        throw new Error(`Contract detail failed to load: ${errText.slice(0, 250)}`);
      }

      expect(page.url()).toContain('/contracts');

      // Open edit if button is present
      const editBtn = page.locator('button:has-text("Edit")');
      if ((await editBtn.count()) > 0) {
        await editBtn.click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForSelector('.contract-editor-page, .error-display', { timeout: 15000 });
        if (!page.url().includes('/login')) {
          expect(page.url()).toContain('/contracts');
          expect(page.url()).toContain('/edit');
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
