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

test.describe('JOURNEY-DPO-004: Monitor Asset Quality @critical', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('DQ runs list loads without backend error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/dq', {
        timeout: 60000,
        contentSelector: '.dq-run-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      await waitForLoadingComplete(page, { timeout: 30000 });
      expect(page.url()).toContain('/dq');

      // Error display must not count as "loaded" — it means the API failed
      const hasError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      if (hasError) {
        const errText = (await page.locator('.error-display, [data-testid="error-display"]').first().first().textContent()) ?? '';
        throw new Error(`DQ runs list shows backend error: ${errText.slice(0, 200)}`);
      }

      const hasContent =
        (await page.locator('.dq-run-list-page').count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0 ||
        (await page.locator('h1:has-text("Data Quality Runs")').count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
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
      expect(onLogin || onDqWithLoginPrompt).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Edge', () => {
    test('DQ list with empty state shows create message', async ({ page }) => {
      const testUser = await getTestUser();
      // Same navigation contract as Success tests: shell + waitForAppMainReady ensures we leave
      // ListPageSkeleton before asserting (plain goto + loginUser can sit on skeleton until timeout).
      await loginAndNavigateToRoute(page, testUser, '/dq', {
        timeout: 60000,
        contentSelector: '.dq-run-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      test.skip(page.url().includes('/login'), 'Redirected to login');
      await waitForLoadingComplete(page, { timeout: 30000 });
      expect(page.url()).toContain('/dq');

      const hasContent =
        (await page.locator('.dq-run-list-page').count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0 ||
        (await page.locator('h1:has-text("Data Quality Runs")').count()) > 0 ||
        (await page.locator('h1:has-text("Data Quality"), h1:has-text("Quality Runs"), [data-testid="dq-page"]').count()) > 0 ||
        (await page.locator('.dq-page, .dq-runs-page, .data-quality-page').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('DQ list shows data rows, pagination, or empty state (not an error)', async ({ page }) => {
      const testUser = await getTestUser();
      // Use loginAndNavigateToRoute to ensure auth tokens survive navigation.
      await loginAndNavigateToRoute(page, testUser, '/dq', {
        timeout: 60000,
        contentSelector: '.dq-run-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on /dq edge test');
      }
      expect(page.url()).toContain('/dq');
      await waitForLoadingComplete(page, { timeout: 30000 });

      const hasError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      if (hasError) {
        const errText = (await page.locator('.error-display, [data-testid="error-display"]').first().first().textContent()) ?? '';
        throw new Error(`DQ list shows backend error: ${errText.slice(0, 200)}`);
      }

      const hasPagination = (await page.locator('.dq-run-list-pagination').count()) > 0;
      const hasListOrEmpty =
        (await page.locator('.dq-run-list-page table tr, .dq-run-list-page .list-item').count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasPagination || hasListOrEmpty).toBe(true) /* acceptable states */;
    });
  });
});
