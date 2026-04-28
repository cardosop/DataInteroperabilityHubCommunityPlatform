/**
 * E2E Test Quality Canary
 *
 * This file validates the E2E test infrastructure itself. It catches false-positive patterns
 * that have historically passed even when the system was broken.
 *
 * Tests here are intentionally minimal and fast — they serve as a canary, not a full suite.
 * If these tests fail, something fundamental is wrong with the test environment or test patterns.
 *
 * Intentionally NOT authentication-gated — these run without login to validate the baseline.
 */

import { expect, test } from '@playwright/test';

test.describe('Test Quality Canary', () => {
  // Force unauthenticated context: canary tests verify baseline auth/routing behavior.
  // Without this, the chromium project's stored storageState would make tests run as an
  // authenticated user, causing the unauthenticated-redirect assertions to fail.
  test.use({ storageState: { cookies: [], origins: [] } });
  test.setTimeout(60000);

  /**
   * A page that redirects (e.g. /protected → /login) should NOT be accepted as a successful
   * page load of the protected route. This catches the pattern:
   *   expect(page.url()).toContain('/protected-or-login')
   * which is always true after visiting a protected route.
   */
  test('canary: unauthenticated request to protected route redirects to login', async ({ page }) => {
    await page.goto('/assets', { waitUntil: 'domcontentloaded' });
    // domcontentloaded fires before React initializes. The SPA auth check runs async:
    // React mounts → reads localStorage (empty) → dispatches redirect to /login.
    // Wait for that redirect to complete before asserting the URL.
    // Use 20s: auth guards may be slow in CI or when initial bundle is large.
    await page.waitForURL(/\/login|\/403/, { timeout: 20000 }).catch(() => {});

    // After navigating to /assets without auth, we must end up on /login
    // (not silently on /assets, which would be a security issue)
    const url = page.url();
    const onLogin = url.includes('/login');
    const onLanding = url === '/' || url.endsWith('/');

    // /assets without auth must redirect — staying on /assets without login would be a security issue
    const stayedOnAssetsWithoutAuth =
      url.includes('/assets') && !url.includes('/login');

    if (stayedOnAssetsWithoutAuth) {
      console.warn(
        '⚠️ Canary: /assets is accessible without authentication — verify auth middleware'
      );
    }

    expect(onLogin || onLanding).toBe(true) /* unauthenticated user must end up on login or landing */;
  });

  /**
   * The login page must render an actual login form, not just exist as a URL.
   * Catches the pattern: expect(page.url()).toContain('/login') after redirect.
   */
  test('canary: login page renders email input (form is present)', async ({ page }) => {
    await page.goto('/login', { waitUntil: 'domcontentloaded' });

    // Must render a login form — URL matching alone is insufficient
    const hasEmailInput =
      (await page.locator('input[type="email"], input#email, input[name="email"]').count()) > 0;
    const hasLoginForm =
      (await page.locator('form, .login-page, [data-testid="login-page"]').count()) > 0;

    expect(
      hasEmailInput || hasLoginForm,
      'Login page must render an email input or login form, not just exist as a URL'
    ).toBe(true);
  });

  /**
   * An intentionally invalid route must show a 404-type response or redirect.
   * Catches the pattern: expect(page.url()).toBeDefined() or expect(url).toMatch(/any-regex/)
   * that would accept any URL as valid.
   */
  test('canary: navigating to a non-existent route does not silently succeed', async ({ page }) => {
    await page.goto('/this-route-absolutely-does-not-exist-e2e-canary-xyz', {
      waitUntil: 'domcontentloaded',
    });
    // domcontentloaded fires before React initializes. The SPA auth check + route resolution
    // run async. For unauthenticated users this redirects to /login; for authenticated users
    // the lazy-loaded NotFoundPage must finish rendering. Wait for either to settle.
    // Use 15s for URL redirect: auth guards may be slow in CI or when initial bundle is large.
    await page.waitForURL(/\/login|\/403|\/not-found|\/404/, { timeout: 15000 }).catch(() => {});
    // If still on the non-existent route, give the lazy 404 bundle time to load
    if (!page.url().includes('/login') && !page.url().includes('/403')) {
      await page.locator('text=/not found|404/i').first().waitFor({ state: 'visible', timeout: 12000 }).catch(() => {});
    }

    const url = page.url();
    // Must either: show 404 content, redirect to login, or redirect to 404 page
    // Must NOT silently show a valid app page (which would mask routing misconfiguration)
    const has404Content =
      (await page.locator('text=/not found|404/i').count()) > 0 ||
      url.includes('/404') ||
      url.includes('/not-found');
    const redirectedToLogin = url.includes('/login');
    const redirectedToHome = url === new URL(page.url()).origin + '/';

    expect(
      has404Content || redirectedToLogin || redirectedToHome,
      'Non-existent route must return 404, redirect to login, or redirect to home — not show a valid page silently'
    ).toBe(true);
  });

  /**
   * The app shell must render after login — basic smoke test for app initialization.
   * If this fails, all other tests that depend on the authenticated app shell will fail.
   * This canary surfaces initialization failures early with a clear failure message.
   *
   * Note: This test is deliberately lightweight. Use it to detect app bootstrap failures,
   * not to test specific features.
   */
  test('canary: app root route responds with a non-empty body', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });

    // Must render SOMETHING — not a blank page
    const bodyText = await page.locator('body').textContent();
    expect(bodyText?.trim().length, 'App root must render non-empty body content').toBeGreaterThan(
      0
    );

    // Must have either a login page or the app shell — not just a blank document
    const hasAppShell =
      (await page
        .locator('.app-sidebar, .app-header, [data-testid="app-header"], .login-page, [data-testid="landing-page"]')
        .count()) > 0;
    expect(
      hasAppShell,
      'App root must render .app-sidebar, .app-header, [data-testid="app-header"], .login-page, or landing-page'
    ).toBe(true);
  });
});
