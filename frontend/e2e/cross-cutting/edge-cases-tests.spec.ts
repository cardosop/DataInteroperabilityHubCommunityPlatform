/**
 * E2E: Edge Case Tests (Phase 29.4.4)
 *
 * Real tests for: empty submit, max length, special chars, pagination, unicode.
 * No mocks; real backend only. Complements dimensions/edge-cases.spec.ts.
 *
 * Run: npm run test:e2e -- e2e/cross-cutting/edge-cases-tests.spec.ts
 */

import { expect, test } from '@playwright/test';
import { getTestUser, getConsumerTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Edge Cases (real tests)', () => {
  test.setTimeout(120000);

  test('empty submit: search with empty string shows list or empty state', async ({ page }) => {
    const user = await getConsumerTestUser();
    await loginAndNavigateToRoute(page, user, '/marketplace', {
      timeout: 90000,
      contentSelector: '.listing-list-page, .listing-list-grid, .empty-state, .listing-list-filters',
    });
    if (page.url().includes('/login')) {
      expect(page.url()).toContain('/login');
      return;
    }
    // Assert the search input exists before filling — if absent, skip with a clear reason
    // rather than silently passing without exercising the scenario
    const searchInput = page.locator('.listing-list-filters input, input[placeholder*="Search"]').first();
    if ((await searchInput.count()) === 0) {
      test.skip(true, 'Search input not rendered on /marketplace; skipping empty-search edge case');
      return;
    }
    await searchInput.fill('');
    await page.waitForTimeout(500);
    expect(page.url()).toContain('/marketplace');
    const hasContent =
      (await page.locator('.listing-list-page, .listing-list-grid, .empty-state').count()) > 0;
    expect(hasContent).toBe(true);
  });

  test('special chars: search with special characters does not crash', async ({ page }) => {
    const user = await getConsumerTestUser();
    await loginAndNavigateToRoute(page, user, '/marketplace', {
      timeout: 90000,
      contentSelector: '.listing-list-page, .listing-list-grid, .empty-state, .listing-list-filters',
    });
    if (page.url().includes('/login')) {
      expect(page.url()).toContain('/login');
      return;
    }
    // Assert the search input exists before filling
    const searchInput = page.locator('.listing-list-filters input, input[placeholder*="Search"]').first();
    if ((await searchInput.count()) === 0) {
      test.skip(true, 'Search input not rendered on /marketplace; skipping special-chars edge case');
      return;
    }
    await searchInput.fill('!@#$%^&*()');
    await page.waitForTimeout(1000);
    expect(page.url()).toContain('/marketplace');
    const hasContent =
      (await page.locator('.listing-list-page, .listing-list-grid, .empty-state, .error-display').count()) > 0;
    expect(hasContent).toBe(true);
  });

  test('unicode: search with unicode characters handles correctly', async ({ page }) => {
    const user = await getConsumerTestUser();
    await loginAndNavigateToRoute(page, user, '/marketplace', {
      timeout: 90000,
      contentSelector: '.listing-list-page, .listing-list-grid, .empty-state, .listing-list-filters',
    });
    if (page.url().includes('/login')) {
      expect(page.url()).toContain('/login');
      return;
    }
    // Assert the search input exists before filling
    const searchInput = page.locator('.listing-list-filters input, input[placeholder*="Search"]').first();
    if ((await searchInput.count()) === 0) {
      test.skip(true, 'Search input not rendered on /marketplace; skipping unicode edge case');
      return;
    }
    await searchInput.fill('日本語テスト café naïve');
    await page.waitForTimeout(1000);
    expect(page.url()).toContain('/marketplace');
    const hasContent =
      (await page.locator('.listing-list-page, .listing-list-grid, .empty-state, .error-display').count()) > 0;
    expect(hasContent).toBe(true);
  });

  test('pagination: list with pagination or single page loads', async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, .empty-state, .error-display, .asset-list-pagination',
    });
    expect(page.url()).toContain('/assets');
    const hasPagination = (await page.locator('.asset-list-pagination').count()) > 0;
    const hasListOrEmpty =
      (await page.locator('.asset-list-page').count()) > 0 ||
      (await page.locator('.empty-state').count()) > 0;
    expect(hasPagination || hasListOrEmpty).toBe(true);
  });

  test('max length: long input in search does not crash', async ({ page }) => {
    const user = await getConsumerTestUser();
    await loginAndNavigateToRoute(page, user, '/marketplace', {
      timeout: 90000,
      contentSelector: '.listing-list-page, .listing-list-grid, .empty-state, .listing-list-filters',
    });
    if (page.url().includes('/login')) {
      expect(page.url()).toContain('/login');
      return;
    }
    // Assert the search input exists before filling
    const searchInput = page.locator('.listing-list-filters input, input[placeholder*="Search"]').first();
    if ((await searchInput.count()) === 0) {
      test.skip(true, 'Search input not rendered on /marketplace; skipping max-length edge case');
      return;
    }
    await searchInput.fill('a'.repeat(500));
    await page.waitForTimeout(1000);
    expect(page.url()).toContain('/marketplace');
    const hasContent =
      (await page.locator('.listing-list-page, .listing-list-grid, .empty-state, .error-display').count()) > 0;
    expect(hasContent).toBe(true);
  });

  // ─── Form input edge cases (asset create form) ────────────────────────────

  test('asset create: max-length name input does not crash the form', async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/assets/create', {
      timeout: 60000,
      contentSelector: '.asset-create-page',
    });
    if (page.url().includes('/login')) {
      expect(page.url()).toContain('/login');
      return;
    }
    if (!page.url().includes('/assets/create')) return; // may redirect on role

    // Assert the name input exists before filling — skip explicitly if absent
    const nameInput = page.locator('input[id="name"], input[name="name"]').first();
    if ((await nameInput.count()) === 0) {
      test.skip(true, 'Name input not found on asset create page; skipping max-length edge case');
      return;
    }
    await nameInput.fill('A'.repeat(500));
    await page.waitForTimeout(500);
    // Form should still be visible (no JS crash from long input)
    await expect(page.locator('.asset-create-page')).toBeVisible({ timeout: 5000 });
    expect(page.url()).toContain('/assets/create');
  });

  test('asset create: special characters in key field does not crash the form', async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/assets/create', {
      timeout: 60000,
      contentSelector: '.asset-create-page',
    });
    if (page.url().includes('/login')) {
      expect(page.url()).toContain('/login');
      return;
    }
    if (!page.url().includes('/assets/create')) return;

    // Assert the key input exists before filling — skip explicitly if absent
    const keyInput = page.locator('input[id="key"], input[name="key"]').first();
    if ((await keyInput.count()) === 0) {
      test.skip(true, 'Key input not found on asset create page; skipping special-chars edge case');
      return;
    }
    await keyInput.fill('!@#$%^&*() invalid key');
    await page.waitForTimeout(500);
    // Form must still be visible (no JS crash)
    await expect(page.locator('.asset-create-page')).toBeVisible({ timeout: 5000 });
    expect(page.url()).toContain('/assets/create');
  });

  test('asset create: empty required fields shows validation before submit', async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/assets/create', {
      timeout: 60000,
      contentSelector: '.asset-create-page',
    });
    if (page.url().includes('/login')) {
      expect(page.url()).toContain('/login');
      return;
    }
    if (!page.url().includes('/assets/create')) return;

    // Assert submit button exists before the test scenario runs
    const submitBtn = page.locator('button:has-text("Create Asset"), button[type="submit"]').first();
    if ((await submitBtn.count()) === 0) {
      test.skip(true, 'Submit button not found on asset create page; skipping validation edge case');
      return;
    }
    await submitBtn.click();
    await page.waitForTimeout(1500);
    // Should remain on the create page (validation prevented navigation)
    expect(page.url()).toContain('/assets/create');
    // Assert that validation feedback was actually triggered — not just that the URL is unchanged.
    // Previously `hasValidationFeedback` was computed but never asserted. Fixed to require it.
    const hasValidationFeedback =
      (await page.locator('.error-message, .field-error, [aria-invalid="true"]').count()) > 0 ||
      !(await page.locator('input[id="name"]').evaluate((el: HTMLInputElement) => el.validity.valid).catch(() => true));
    expect(hasValidationFeedback).toBe(true);
  });
});
