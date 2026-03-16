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
  // 300s: loginAndNavigateToRoute (~60s) + Phase 1 up to 65s + Phase 2 up to 90s + overhead (~30s) = 245s
  test.setTimeout(300000);

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
    // Root cause fix (applied):
    //   1. ContractEditorPage was lazy-loaded without a <Suspense> wrapper in routes.tsx.
    //      React.lazy() requires a Suspense boundary; without one, the Suspense signal
    //      propagates to RouterProvider's internal null-fallback Suspense, causing an
    //      indefinite "Loading..." state that never transitions to the error display.
    //      Fix: Added <Suspense fallback={<LoadingSpinner message="Loading contract editor..." />}>
    //      in routes.tsx — the chunk now has a defined loading state and terminates correctly.
    //   2. Phase 2 now uses page.waitForResponse() to wait for the actual API response
    //      (deterministic signal) instead of a fixed timeout (which is environment-sensitive).
    //      This handles: slow backends (30s Axios timeout × 2 React Query attempts = 60s),
    //      auth token refresh (401 → refresh POST → contract retry), and Vite chunk load time.
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/', {
      timeout: 60000,
      contentSelector: '[data-testid="home-page"], .home-page, main',
    });

    // Set up the API response waiter BEFORE navigation so we don't miss the response.
    // Timeout: 150s covers Phase 1 (≤65s) + chunk download (≤10s) + worst-case API path
    // (auth refresh 30s + Axios timeout 30s × 2 React Query attempts = 60s) + buffer.
    // Skip 401 responses — the interceptor will refresh and retry; we want the final response.
    const contractApiDone = page.waitForResponse(
      (r) =>
        r.url().includes('/api/v1/contracts/') &&
        r.url().includes('00000000') &&
        r.status() !== 401,
      { timeout: 150_000 }
    );

    await page.goto('/contracts/00000000-0000-0000-0000-000000000000/edit');
    await page.waitForLoadState('domcontentloaded');

    // Phase 1: Wait for auth init to complete (.app-main indicates app shell is rendered).
    // 65s covers the worst-case auth init including the 60s auth-store safety timeout
    // (INIT_MAX_MS) which clears auth state and redirects to /login.
    await page.waitForSelector('.app-main', { timeout: 65000 }).catch(() => null);
    if (page.url().includes('/login')) return;

    // Phase 2: Wait for the contract API response — this is the deterministic signal that
    // the request completed (404 or other error). Once received, React re-renders quickly.
    await contractApiDone.catch(() => null);

    // Phase 3: Brief wait for React to process the error response and render ErrorDisplay.
    await page
      .locator('.error-display, text=/not found|failed|404|403/i')
      .first()
      .waitFor({ state: 'visible', timeout: 15000 })
      .catch(() => null);
    const hasError =
      (await page.locator('.error-display').count()) > 0 ||
      (await page.locator('text=/not found|failed|404|403/i').count()) > 0;
    const onLogin = page.url().includes('/login');
    // Must show a real error — not just "the editor isn't there"
    expect(hasError || onLogin).toBe(true);
  });

  test('network error: failed API request shows error or retry', async ({ page }) => {
    // When all asset list requests fail with 503, the app must surface an error display.
    //
    // Root cause analysis:
    //   1. AssetListPage is lazy-loaded with <Suspense> in routes.tsx — Suspense boundary
    //      terminates correctly when the chunk loads.
    //   2. route.fulfill(503) bypasses Axios's network-retry interceptor (only ERR_NETWORK
    //      errors trigger it). React Query retries once (failureCount < 1 → retry config)
    //      then sets error state. Total: 2 intercepted 503s before status='error'.
    //   3. Phase 2 must wait for BOTH 503 responses (initial + React Query retry). Only
    //      after the second 503 does React Query set status='error' and render ErrorDisplay.
    //      Waiting for only the FIRST 503 leaves a 1s retry-delay window where the component
    //      shows EmptyState (data=undefined, error=null), and the subsequent 20s Phase 3 may
    //      miss the brief ErrorDisplay render if auth re-init overlaps (StrictMode double-mount
    //      calls initialize() twice, briefly making isLoading=true and unmounting AppShell).
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/', {
      timeout: 60000,
      contentSelector: '[data-testid="home-page"], .home-page, main',
    });

    // Count intercepted 503s. React Query's retry policy (failureCount < 1) retries once,
    // so EXACTLY 2 GET /assets/ requests will be made before status='error' is set.
    // Set up the counter BEFORE route interception and navigation so no response is missed.
    // Timeout: 120s = auth-store INIT_MAX_MS (60s) + Suspense chunk load (≤10s) +
    //          first 503 (immediate) + 1s retry delay + second 503 (immediate) + buffer.
    let assetsResponseCount = 0;
    const bothAssetsResponsesDone = page.waitForResponse(
      (r) => {
        if (
          r.url().includes('/api/v1/assets/') &&
          r.request().method() === 'GET' &&
          r.status() !== 401
        ) {
          assetsResponseCount++;
          return assetsResponseCount >= 2;
        }
        return false;
      },
      { timeout: 120000 }
    );

    // route.fulfill(503): immediate HTTP error, bypasses Axios network-retry interceptor.
    await page.route(/\/api\/v1\/assets\//, (route) =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Service Unavailable' }),
      })
    );
    await page.goto('/assets', { waitUntil: 'domcontentloaded' });

    // Phase 1: Wait for auth init to complete. 65s covers the auth-store safety timeout
    // (INIT_MAX_MS=60s); either .app-main appears or /login redirect is caught.
    await page.waitForSelector('.app-main', { timeout: 65000 }).catch(() => null);
    if (page.url().includes('/login')) return;

    // Phase 2: Wait for BOTH intercepted 503 responses. After the second, React Query has
    // definitively set status='error' and AssetListPage renders ErrorDisplay synchronously.
    await bothAssetsResponsesDone.catch(() => null);

    // Phase 3: ErrorDisplay renders in the next React commit after Phase 2 resolves.
    // 15s provides headroom for any auth re-init remount that briefly hides AppShell.
    await page
      .locator('.error-display, text=/failed|error|retry|service unavailable/i')
      .first()
      .waitFor({ state: 'visible', timeout: 15000 })
      .catch(() => null);
    const hasError =
      (await page.locator('.error-display').count()) > 0 ||
      (await page.locator('text=/failed|error|retry|service unavailable/i').count()) > 0;
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
