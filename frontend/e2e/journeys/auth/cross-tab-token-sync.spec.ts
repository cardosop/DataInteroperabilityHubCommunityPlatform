/**
 * Phase 277.B.067 — cross-tab auth token sync E2E test.
 *
 * The sync mechanism (``useCrossTabAuthSync``, mounted once in
 * RootRoute) reacts to ``storage`` events on the ``access_token`` key:
 *
 *   * login in tab A  → tab B adopts the token + re-initializes auth
 *   * logout in tab A → tab B clears the session (app-shell unmounts;
 *     at the public root the landing page renders — the listener's
 *     /login navigation can bounce back to / via RootRoute)
 *
 * Test 2 pins the LISTENER (tab B loses its authenticated state
 * without navigating itself — shared localStorage alone cannot
 * re-render a mounted page); test 1 asserts the propagated auth
 * state on a protected route.
 *
 * Selector contract: the login submit button publishes
 * ``data-testid="login-submit"`` (do NOT match its label — it was
 * renamed Sign in → Login and the accessible-name matcher timed out
 * for 120s). The user menu button carries ``aria-label="User menu"``;
 * the logout item is ``role="menuitem"`` named "Logout" (no space).
 *
 * The persona is deliberately DIFFERENT from the storageState user
 * (getTestUser) so the login in tab A produces a new access_token —
 * a storage event only fires when the value actually changes.
 */
import { test, expect } from '@playwright/test';

import { getComplianceOfficerUser } from '../../fixtures/auth';

async function loginInTab(
  tab: import('@playwright/test').Page,
  user: Awaited<ReturnType<typeof getComplianceOfficerUser>>,
): Promise<void> {
  await tab.goto('/login');
  await tab.getByLabel('Email').fill(user.email);
  await tab.getByLabel('Password').fill(user.password);
  await tab.getByTestId('login-submit').click();
  // Post-login the app renders the app shell at / (there is no
  // /dashboard route — a waitForURL(/\/dashboard/) never resolves).
  await expect(tab.getByTestId('app-shell')).toBeVisible({ timeout: 20_000 });
}

test.describe('Cross-Tab Auth Token Sync', () => {
  test('login in tab A propagates to tab B via storage event', async ({
    context,
  }) => {
    const user = await getComplianceOfficerUser();
    const tabA = await context.newPage();
    const tabB = await context.newPage();

    // Tab B sits on the login page while tab A logs in.
    await tabB.goto('/login');
    await loginInTab(tabA, user);

    // Tab B picks up the propagated auth state (listener adoption +
    // shared localStorage) and renders the protected app shell.
    await tabB.goto('/');
    await expect(tabB.getByTestId('app-shell')).toBeVisible({
      timeout: 20_000,
    });

    await tabA.close();
    await tabB.close();
  });

  test('logout in tab A propagates to tab B via storage event', async ({
    context,
  }) => {
    const user = await getComplianceOfficerUser();
    const tabA = await context.newPage();
    const tabB = await context.newPage();

    await loginInTab(tabA, user);

    // Tab B reaches the app shell through the propagated auth state.
    await tabB.goto('/');
    await expect(tabB.getByTestId('app-shell')).toBeVisible({
      timeout: 20_000,
    });
    // Settle: tab B's token adoption runs initializeAuth() asynchronously.
    // Logging out while it is still in flight races the logout's storage
    // events (the in-flight /auth/me/ can land after the clear). Give the
    // adoption a beat to finish — the propagation this test pins is the
    // STORAGE-EVENT clear that the logout events themselves trigger.
    await tabB.waitForTimeout(1500);

    // Tab A logs out: clearAuth() removes access_token → storage event
    // → tab B's listener clears the session WITHOUT tab B navigating
    // itself — this pins the listener, not just the shared localStorage.
    //
    // URL contract: the listener also navigates to /login, but RootRoute
    // re-renders with the cleared store and the PUBLIC root renders the
    // Landing page at '/' (a bounced /login redirect can land back at
    // /). So the URL is not a stable contract — the SECURITY property
    // is: a rendered, previously-authenticated tab loses its session.
    // Assert app-shell unmounts in BOTH tabs and tab B shows the
    // unauthenticated UI (login form or landing sign-in link).
    await tabA.getByRole('button', { name: 'User menu' }).click();
    await tabA.getByRole('menuitem', { name: 'Logout' }).click();
    await expect(tabA.getByTestId('app-shell')).toHaveCount(0);
    await expect(tabB.getByTestId('app-shell')).toHaveCount(0, { timeout: 20_000 });
    const unauthenticatedUI = tabB
      .getByLabel('Email')
      .or(tabB.getByRole('button', { name: /log ?in/i }))
      .or(tabB.getByRole('link', { name: /sign in/i }));
    await expect(unauthenticatedUI.first()).toBeVisible({ timeout: 10_000 });

    await tabA.close();
    await tabB.close();
  });
});
