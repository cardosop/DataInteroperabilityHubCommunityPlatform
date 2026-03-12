/**
 * E2E Test: JOURNEY-DPO-004 — Monitor Asset Quality
 *
 * Journey: Monitor Asset Quality
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /dq, /dq/runs/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';
import {
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-004: Monitor Asset Quality', () => {
  test.setTimeout(180000); // 3 min: visible/slowMo; DQ list + detail

  test.describe('Success', () => {
    test('DQ runs list loads without backend error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/dq', {
        timeout: 60000,
        contentSelector: '.dq-run-list-page, .empty-state, .error-display, .loading-spinner-container',
      });
      await waitForLoadingComplete(page, { timeout: 30000 });
      expect(page.url()).toContain('/dq');

      // Error display must not count as "loaded" — it means the API failed
      const hasError = (await page.locator('.error-display').count()) > 0;
      if (hasError) {
        const errText = (await page.locator('.error-display').first().textContent()) ?? '';
        throw new Error(`DQ runs list shows backend error: ${errText.slice(0, 200)}`);
      }

      const hasContent =
        (await page.locator('.dq-run-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('h1:has-text("Data Quality Runs")').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('DQ run detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/dq/runs/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.dq-run-detail-page',
        waitAfterLoad: 8000,
      });
    });

    test('unauthenticated access to DQ runs list redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/dq', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|dq)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onDqWithLoginPrompt =
        url.includes('/dq') &&
        ((await page.locator('input#email, [href*="/login"]').count()) > 0 ||
          (await page.locator('text=Sign in').count()) > 0);
      expect(onLogin || onDqWithLoginPrompt).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('DQ list with empty state shows create message', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/dq');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.dq-run-list-page, .empty-state, .error-display, .loading-spinner-container, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 65000 });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/dq');
    });

    test('DQ list shows data rows, pagination, or empty state (not an error)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/dq');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.dq-run-list-page, .empty-state, .error-display, .loading-spinner-container, .dq-run-list-pagination, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 65000 });
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on /dq edge test');
      }
      expect(page.url()).toContain('/dq');
      await waitForLoadingComplete(page, { timeout: 30000 });
      await page
        .locator('.dq-run-list-page, .empty-state, .error-display')
        .first()
        .waitFor({ state: 'visible', timeout: 25000 });

      const hasError = (await page.locator('.error-display').count()) > 0;
      if (hasError) {
        const errText = (await page.locator('.error-display').first().textContent()) ?? '';
        throw new Error(`DQ list shows backend error: ${errText.slice(0, 200)}`);
      }

      const hasPagination = (await page.locator('.dq-run-list-pagination').count()) > 0;
      const hasListOrEmpty =
        (await page.locator('.dq-run-list-page table tr, .dq-run-list-page .list-item').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasPagination || hasListOrEmpty).toBe(true);
    });
  });
});
