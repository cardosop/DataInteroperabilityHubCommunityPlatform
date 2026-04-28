/**
 * JOURNEY-AUTH-SECURITY — Phase 11.1 Browser-side token storage verification
 *
 * Verifies that the access token is NOT present in localStorage after login
 * (it lives in JS module memory only) and that the refresh_token cookie is
 * marked httpOnly (i.e. invisible to document.cookie).
 */

import { expect, test } from '@playwright/test';
import { loginUser } from '../../fixtures/auth';
import { ensureTestUser } from '../../setup/create-test-user';

// Run serially: all four tests call loginUser({forceFreshLogin, failOnFallback}) which
// drives a real UI login.  Parallel execution races against the auth rate-limiter causing
// /auth/me/ 429s that make localStorage.user never get written.  Serial mode costs ~10s
// total but removes the flakiness completely.
test.describe.configure({ mode: 'serial' });

test.describe('JOURNEY-AUTH-SECURITY: token storage hardening (11.1)', () => {
  test('access_token absent from localStorage after UI login', async ({ page }) => {
    const user = await ensureTestUser();

    // Perform a real UI login (not API injection) to exercise the actual login flow.
    await loginUser(page, user, { forceFreshLogin: true, failOnFallback: true });

    const accessTokenInStorage = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );

    // After a fresh UI login the access token must not be in localStorage.
    // (E2E injection via loginViaApiAndInject still writes it, but UI login must not.)
    expect(accessTokenInStorage).toBeNull();
  });

  test('refresh_token cookie invisible to JavaScript (httpOnly)', async ({ page }) => {
    const user = await ensureTestUser();
    await loginUser(page, user, { forceFreshLogin: true, failOnFallback: true });

    const cookieVisibleToJs = await page.evaluate(() =>
      document.cookie
        .split(';')
        .map((c) => c.trim())
        .some((c) => c.startsWith('refresh_token='))
    );

    // httpOnly cookies are invisible to document.cookie
    expect(cookieVisibleToJs).toBe(false);
  });

  test('user profile remains in localStorage for session detection', async ({ page }) => {
    const user = await ensureTestUser();
    await loginUser(page, user, { forceFreshLogin: true, failOnFallback: true });

    const userInStorage = await page.evaluate(() => localStorage.getItem('user'));
    expect(userInStorage).not.toBeNull();

    const parsed = JSON.parse(userInStorage!);
    expect(parsed.email).toBe(user.email);
  });

  test('app shell loads without access_token in localStorage (session from cookie)', async ({
    page,
  }) => {
    const user = await ensureTestUser();
    await loginUser(page, user, { forceFreshLogin: true, failOnFallback: true });

    // Remove access_token from localStorage to simulate a page reload after 11.1
    // where access_token was never written there.  The app should still boot via
    // the refresh-token cookie silent-refresh path.
    await page.evaluate(() => localStorage.removeItem('access_token'));
    await page.reload({ waitUntil: 'domcontentloaded' });

    // App shell should appear (the silent refresh restored the session).
    const shell = page.locator('.app-sidebar, .app-header, [data-testid="app-header"]').first();
    await expect(shell).toBeVisible({ timeout: 60_000 });
  });
});
