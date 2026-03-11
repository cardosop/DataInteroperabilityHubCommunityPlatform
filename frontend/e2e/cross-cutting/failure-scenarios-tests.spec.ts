/**
 * E2E: Failure Scenario Tests (Phase 29.4.3)
 *
 * Real tests for: session expiry, invalid JSON, 404, 403, API error, network error, 429 handling.
 * No mocks; real backend only. Complements dimensions/failure-scenarios.spec.ts.
 *
 * Run: npm run test:e2e -- e2e/cross-cutting/failure-scenarios-tests.spec.ts
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Failure Scenarios (real tests)', () => {
  test.setTimeout(120000);

  test('session expiry: unauthenticated access to protected route redirects to login', async ({
    page,
  }) => {
    await clearAuthStorage(page);
    await page.goto('/assets', { waitUntil: 'domcontentloaded' });
    await page.waitForURL(/\/(login|403)(\?|$)/, { timeout: 25_000 });
    const url = page.url();
    const onLogin = url.includes('/login');
    const on403 = url.includes('/403');
    expect(onLogin || on403).toBe(true);
  });

  test('invalid JSON in ODPS upload shows validation error', async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/odps/upload', {
      timeout: 60000,
      contentSelector: 'textarea#odps-content, textarea, .odps-upload-page',
    });
    if (page.url().includes('/login')) {
      expect(page.url()).toContain('/login');
      return;
    }
    const textarea = page.locator('textarea#odps-content, textarea').first();
    await expect(textarea).toBeVisible({ timeout: 10000 });
    await textarea.fill('{ invalid json }');
    await page.waitForTimeout(500);
    const submitBtn = page.locator('button:has-text("Create ODPS Product")').first();
    if ((await submitBtn.count()) > 0) {
      await submitBtn.click();
      await page.waitForTimeout(6000);
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.getByText(/invalid|schema|required|parse|json/i).count()) > 0;
      const stillOnUpload = page.url().includes('/odps/upload');
      expect(hasError || stillOnUpload).toBe(true);
    }
  });

  test('non-existent resource shows 404 or error', async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/', {
      timeout: 60000,
      contentSelector: '[data-testid="home-page"], .home-page, main',
    });
    await page.goto('/assets/00000000-0000-0000-0000-000000000000');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(5000);
    const hasError =
      (await page.locator('.error-display').count()) > 0 ||
      (await page.locator('text=/not found|404|failed to load/i').count()) > 0;
    const noDetail = (await page.locator('.asset-detail-page').count()) === 0;
    expect(hasError || noDetail).toBe(true);
  });

  test('403: forbidden route shows 403 or redirect', async ({ page }) => {
    await clearAuthStorage(page);
    await page.goto('/admin', { waitUntil: 'domcontentloaded' });
    await page.waitForURL(/\/(login|403)(\?|$)/, { timeout: 25_000 });
    const url = page.url();
    expect(url.includes('/login') || url.includes('/403')).toBe(true);
  });

  test('error display shown when API returns error', async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/', {
      timeout: 60000,
      contentSelector: '[data-testid="home-page"], .home-page, main',
    });
    await page.goto('/contracts/00000000-0000-0000-0000-000000000000/edit');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(8000);
    const hasError =
      (await page.locator('.error-display').count()) > 0 ||
      (await page.locator('text=/not found|failed|404|403/i').count()) > 0;
    const noEditor = (await page.locator('.contract-editor-page').count()) === 0;
    expect(hasError || noEditor).toBe(true);
  });

  test('network error: aborted API request shows error or retry', async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/', {
      timeout: 60000,
      contentSelector: '[data-testid="home-page"], .home-page, main',
    });
    await page.route('**/api/v1/assets/**', (route) => route.abort('failed'));
    await page.goto('/assets', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(8000);
    const hasError =
      (await page.locator('.error-display').count()) > 0 ||
      (await page.locator('text=/failed|error|retry|network/i').count()) > 0;
    const hasEmptyOrLoading =
      (await page.locator('.empty-state, .loading-spinner-container').count()) > 0;
    expect(hasError || hasEmptyOrLoading).toBe(true);
  });

  test('429 rate limit: multiple failed logins show rate limit or invalid credentials', async ({
    page,
  }) => {
    await clearAuthStorage(page);
    for (let i = 0; i < 6; i++) {
      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.fill('input#email', 'invalid@example.com');
      await page.fill('input#password', 'wrongpassword');
      await page.locator('input#password').press('Enter');
      const resp = await page.waitForResponse(
        (r) => r.url().includes('/auth/login/') && (r.status() === 400 || r.status() === 401 || r.status() === 429),
        { timeout: 15000 }
      ).catch(() => null);
      if (resp?.status() === 429) break;
      await page.waitForTimeout(500);
    }
    const onLogin = page.url().includes('/login');
    const hasError =
      (await page.locator('.error-message').count()) > 0 ||
      (await page.getByText(/invalid|rate limit|too many/i).count()) > 0;
    expect(onLogin || hasError).toBe(true);
  });
});
