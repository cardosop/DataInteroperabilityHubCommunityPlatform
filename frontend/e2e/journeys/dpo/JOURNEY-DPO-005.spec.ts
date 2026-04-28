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
import { createODCSContractViaApi } from '../../fixtures/api-assets';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-005: Configure Data Contracts @critical', () => {
  test.setTimeout(120000); // 2 min default per test; individual tests override when needed

  test.describe('Success', () => {
    test('contracts list loads without backend error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1',
      });
      expect(page.url()).toContain('/contracts');
      await waitForLoadingComplete(page, { timeout: 30000 });

      // Error display must NOT count as "contracts list loaded" — it means the API failed
      const hasError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      if (hasError) {
        const errText = (await page.locator('.error-display, [data-testid="error-display"]').first().first().textContent()) ?? '';
        throw new Error(`Contracts list shows backend error: ${errText.slice(0, 200)}`);
      }

      const hasContent =
        (await page.locator('.contract-list-page, [data-testid="contract-list-page"]').first().count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
    });

    test('contract detail page loads for a known contract (API-seeded)', async ({ page }) => {
      // Seed a contract via API so the test never vacuously skips due to an empty catalog.
      // Navigate directly using the known contractId — avoids relying on list link structure.
      const testUser = await getTestUser();
      const contractId = await createODCSContractViaApi(testUser);

      // Navigate directly to the contract detail URL using the seeded ID
      await loginAndNavigateToRoute(page, testUser, `/contracts/${contractId}`, {
        timeout: 90000,
        contentSelector: '.contract-detail-page, [data-testid="contract-detail-page"], .contract-detail-content, .error-display, [data-testid="error-display"]',
      });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on contract detail');
      }

      const hasError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      if (hasError) {
        const errText = (await page.locator('.error-display, [data-testid="error-display"]').first().first().textContent()) ?? '';
        throw new Error(`Contract detail failed to load: ${errText.slice(0, 250)}`);
      }

      expect(page.url()).toContain('/contracts');

      // Open edit if button is present
      const editBtn = page.locator('button:has-text("Edit")');
      // intentional: edit affordance is role-conditional — read-only roles legitimately don't see it.
      if ((await editBtn.count()) > 0) {
        await editBtn.click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForSelector('.contract-editor-page, .error-display, [data-testid="error-display"]', { timeout: 15000 });
        if (page.url().includes('/login')) {
          throw new Error('Unexpected redirect to login after clicking Edit on contract detail');
        }
        expect(page.url()).toContain('/contracts');
        expect(page.url()).toContain('/edit');
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
        detailContentSelector: '.contract-editor-page, .contract-detail-page, [data-testid="contract-detail-page"]',
        waitAfterLoad: 8000,
        selectorTimeout: 60000,
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
      expect(onLogin || onContractsWithLoginPrompt).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Edge', () => {
    test('contracts list loads with empty state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 90000,
        contentSelector: '.contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1',
      });
      if (page.url().includes('/login')) {
        throw new Error('Contracts list redirected to login; auth may have failed under parallel load.');
      }
      expect(page.url()).toContain('/contracts');

      const hasContent =
        (await page.locator('.contract-list-page, [data-testid="contract-list-page"]').first().count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('contracts list shows data rows, pagination, or empty state (not an error)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 90000,
        contentSelector: '.contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], .contract-list-pagination, h1',
      });
      if (page.url().includes('/login')) {
        throw new Error('Contracts list redirected to login; auth may have failed under parallel load.');
      }
      expect(page.url()).toContain('/contracts');
      await page
        .locator('.contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 });

      const hasError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      if (hasError) {
        const errText = (await page.locator('.error-display, [data-testid="error-display"]').first().first().textContent()) ?? '';
        throw new Error(`Contracts list shows backend error: ${errText.slice(0, 200)}`);
      }

      const hasPagination = (await page.locator('.contract-list-pagination').count()) > 0;
      const hasListOrEmpty =
        (await page.locator('.contract-list-page, [data-testid="contract-list-page"] table tr, .contract-list-page, [data-testid="contract-list-page"] .list-item, .contract-list-page, [data-testid="contract-list-page"] a[href*="/contracts/"]').count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasPagination || hasListOrEmpty).toBe(true) /* acceptable states */;
    });
  });
});
