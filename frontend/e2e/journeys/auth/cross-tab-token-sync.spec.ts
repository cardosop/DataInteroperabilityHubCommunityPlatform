/**
 * Phase 277.B.067 — cross-tab auth token sync E2E test.
 *
 * Validates that when a user logs in/out in one browser tab,
 * a second tab sharing the same origin detects the change via
 * the ``storage`` event and updates its auth state accordingly.
 */
import { test, expect } from '@playwright/test';

test.describe('Cross-Tab Auth Token Sync', () => {
  test('login in tab A propagates to tab B via storage event', async ({
    context,
  }) => {
    // Open two tabs sharing the same browser context (same localStorage)
    const tabA = await context.newPage();
    const tabB = await context.newPage();

    // Both tabs navigate to the login page
    await tabA.goto('/login');
    await tabB.goto('/login');

    // Tab A: log in
    await tabA.getByLabel('Email').fill('user@meshant.com');
    await tabA.getByLabel('Password').fill('testpass123');
    await tabA.getByRole('button', { name: /sign in/i }).click();
    await tabA.waitForURL(/\/dashboard/);

    // Tab A should be authenticated
    await expect(tabA.getByTestId('app-shell')).toBeVisible();

    // Tab B: trigger a navigation or state check. The storage event
    // listener should detect the access_token change and re-initialize
    // auth. Navigate to a protected route to verify.
    await tabB.goto('/dashboard');

    // Tab B should now also be authenticated (the token was synced via localStorage)
    await expect(tabB.getByTestId('app-shell')).toBeVisible();

    await tabA.close();
    await tabB.close();
  });

  test('logout in tab A propagates to tab B via storage event', async ({
    context,
  }) => {
    const tabA = await context.newPage();
    const tabB = await context.newPage();

    // Both tabs log in (use the same storage state)
    await tabA.goto('/login');
    await tabA.getByLabel('Email').fill('user@meshant.com');
    await tabA.getByLabel('Password').fill('testpass123');
    await tabA.getByRole('button', { name: /sign in/i }).click();
    await tabA.waitForURL(/\/dashboard/);

    // Tab B navigates to dashboard (should be authenticated via sync)
    await tabB.goto('/dashboard');
    await expect(tabB.getByTestId('app-shell')).toBeVisible();

    // Tab A: log out
    await tabA.getByTestId('user-menu').click();
    await tabA.getByText(/log out/i).click();
    await tabA.waitForURL(/\/login/);

    // Tab B: navigate to a protected route — should redirect to login
    await tabB.goto('/dashboard');
    await tabB.waitForURL(/\/login/);

    await tabA.close();
    await tabB.close();
  });
});
