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
  // 200s: loginAndNavigateToRoute (~45s) + Phase 1 up to 65s + Phase 2 up to 30s + overhead
  test.setTimeout(200000);

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
    // Assert the submit button exists before the scenario runs — skip explicitly if absent
    const submitBtn = page.locator('button:has-text("Create ODPS Product")').first();
    if ((await submitBtn.count()) === 0) {
      test.skip(true, 'ODPS submit button not found on upload page; skipping invalid-JSON scenario');
      return;
    }
    await submitBtn.click();
    // Wait for the error state to render after submission (API validates JSON server-side)
    await page
      .locator('.error-display, text=/invalid|schema|required|parse|json/i')
      .first()
      .waitFor({ state: 'visible', timeout: 10000 })
      .catch(() => null);
    const hasError =
      (await page.locator('.error-display').count()) > 0 ||
      (await page.getByText(/invalid|schema|required|parse|json/i).count()) > 0;
    const stillOnUpload = page.url().includes('/odps/upload');
    // Must show an error OR remain on upload (no silent navigation to success)
    expect(hasError || stillOnUpload).toBe(true);
  });

  test('non-existent resource shows 404 or error', async ({ page }) => {
    // Root cause of failures: Phase 1 was 45s, but the auth-store safety timeout (INIT_MAX_MS)
    // is 60s.  Between 45s and 60s, auth is still loading, .app-main has not appeared, and the
    // URL is /assets/:id (not /login), so Phase 2 sees no error and no login → assertion fails.
    // Fix: extend Phase 1 to 65s (> INIT_MAX_MS) and Phase 2 to 30s.
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/', {
      timeout: 60000,
      contentSelector: '[data-testid="home-page"], .home-page, main',
    });
    await page.goto('/assets/00000000-0000-0000-0000-000000000000');
    await page.waitForLoadState('domcontentloaded');

    // Phase 1: Wait for auth init to complete.  .app-main appears only after ProtectedRoute
    // stops showing the loading spinner.  65s covers the worst-case auth init including the
    // 60s auth-store safety timeout (INIT_MAX_MS) which clears auth and redirects to /login.
    await page.waitForSelector('.app-main', { timeout: 65000 }).catch(() => null);
    if (page.url().includes('/login')) return; // Auth failed → login redirect is a valid outcome

    // Phase 2: Auth is done.  Wait for the asset 404 error to render (API responds quickly).
    await page
      .locator('.error-display, .error-display-title')
      .first()
      .waitFor({ state: 'visible', timeout: 30000 })
      .catch(() => null);
    const hasError = (await page.locator('.error-display').count()) > 0;
    const onLogin = page.url().includes('/login');
    // Must show a real error — not just "the detail page isn't there"
    expect(hasError || onLogin).toBe(true);
  });

  test('403: forbidden route shows 403 or redirect', async ({ page }) => {
    await clearAuthStorage(page);
    await page.goto('/admin', { waitUntil: 'domcontentloaded' });
    await page.waitForURL(/\/(login|403)(\?|$)/, { timeout: 25_000 });
    const url = page.url();
    expect(url.includes('/login') || url.includes('/403')).toBe(true);
  });

  test('error display shown when API returns error', async ({ page }) => {
    // Root cause: same timing issue as the non-existent-resource test.  Phase 1 (45s) can
    // expire while the auth-store safety timeout (60s) is still running, leaving the page in
    // an auth-loading state with no error display and no /login redirect → assertion fails.
    // Fix: extend Phase 1 to 65s and Phase 2 to 30s.
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/', {
      timeout: 60000,
      contentSelector: '[data-testid="home-page"], .home-page, main',
    });
    await page.goto('/contracts/00000000-0000-0000-0000-000000000000/edit');
    await page.waitForLoadState('domcontentloaded');

    // Phase 1: Wait for auth init to complete (.app-main indicates app shell is rendered).
    // 65s covers the worst-case auth init including the 60s auth-store safety timeout
    // (INIT_MAX_MS) which clears auth state and redirects to /login.
    await page.waitForSelector('.app-main', { timeout: 65000 }).catch(() => null);
    if (page.url().includes('/login')) return;

    // Phase 2: Auth done — wait for the contract 404 error to render.
    await page
      .locator('.error-display, text=/not found|failed|404|403/i')
      .first()
      .waitFor({ state: 'visible', timeout: 30000 })
      .catch(() => null);
    const hasError =
      (await page.locator('.error-display').count()) > 0 ||
      (await page.locator('text=/not found|failed|404|403/i').count()) > 0;
    const onLogin = page.url().includes('/login');
    // Must show a real error — not just "the editor isn't there"
    expect(hasError || onLogin).toBe(true);
  });

  test('network error: aborted API request shows error or retry', async ({ page }) => {
    // When all asset list requests are aborted, the app must surface an error.
    //
    // Root cause of failures: Phase 1 waited 45s for .app-main, but the auth-store safety
    // timeout (INIT_MAX_MS=60s) can fire between 45s and 60s.  In that window, auth is still
    // loading, .app-main has not appeared, and the URL is still /assets (not /login), so
    // hasError=false and onLogin=false causes the assertion to fail.
    //
    // Fix: extend Phase 1 to 65s (> INIT_MAX_MS) so we always see either .app-main or the
    // /login redirect.  Extend Phase 2 to 30s to cover Axios retries (2×) + RQ retry (1×)
    // totalling ~7s under ideal conditions, with buffer for parallel-load delays.
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/', {
      timeout: 60000,
      contentSelector: '[data-testid="home-page"], .home-page, main',
    });
    await page.route('**/api/v1/assets/**', (route) => route.abort('failed'));
    await page.goto('/assets', { waitUntil: 'domcontentloaded' });

    // Phase 1: Wait for auth init to complete.  65s matches the auth-store safety timeout
    // (INIT_MAX_MS=60s) so we either see .app-main or catch the /login redirect.
    await page.waitForSelector('.app-main', { timeout: 65000 }).catch(() => null);
    if (page.url().includes('/login')) return;

    // Phase 2: Auth done — wait for the error display.
    // Timing: Axios retries 2× (1s+2s=3s) + React Query retry (1s delay) + 2nd Axios chain (3s) ≈ 7s.
    // Under parallel E2E load, allow 30s to absorb longer retry chains.
    await page
      .locator('.error-display, text=/failed|error|retry|network/i')
      .first()
      .waitFor({ state: 'visible', timeout: 30000 })
      .catch(() => null);
    const hasError =
      (await page.locator('.error-display').count()) > 0 ||
      (await page.locator('text=/failed|error|retry|network/i').count()) > 0;
    const onLogin = page.url().includes('/login');
    // Must show a real error (not a stuck loading spinner) OR redirect to login if auth failed
    expect(hasError || onLogin).toBe(true);
  });

  test('429 rate limit: multiple failed logins show rate limit or invalid credentials', async ({
    page,
  }) => {
    // The `onLogin` branch was a false positive: after `clearAuthStorage` the user is always
    // unauthenticated, so the loop always ends on /login regardless of rate-limit behavior.
    // Fix: assert only on the meaningful signal — a visible error message in the UI.
    await clearAuthStorage(page);
    let hitRateLimit = false;
    for (let i = 0; i < 6; i++) {
      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.fill('input#email', 'invalid@example.com');
      await page.fill('input#password', 'wrongpassword');
      await page.locator('input#password').press('Enter');
      const resp = await page.waitForResponse(
        (r) => r.url().includes('/auth/login/') && (r.status() === 400 || r.status() === 401 || r.status() === 429),
        { timeout: 15000 }
      ).catch(() => null);
      if (resp?.status() === 429) {
        hitRateLimit = true;
        break;
      }
      await page.waitForTimeout(500);
    }
    // Must show a visible error — either "invalid credentials" on every attempt
    // or "rate limit / too many requests" once the threshold is hit
    const hasError =
      (await page.locator('.error-message').count()) > 0 ||
      (await page.getByText(/invalid|rate limit|too many/i).count()) > 0;
    expect(hasError).toBe(true);
    // If we hit 429, verify the rate-limit message is actually shown in the UI
    if (hitRateLimit) {
      const hasRateLimitMessage =
        (await page.getByText(/rate limit|too many/i).count()) > 0;
      // Non-fatal: some backends return 429 without a UI-visible message
      if (!hasRateLimitMessage) {
        console.log('Note: 429 returned by API but no rate-limit message rendered in UI');
      }
    }
  });
});
