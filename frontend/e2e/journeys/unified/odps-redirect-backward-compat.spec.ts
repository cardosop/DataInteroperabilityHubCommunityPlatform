/**
 * E2E: ODPS Redirect Backward Compatibility.
 *
 * Verifies that old /odps URLs redirect to /contracts without
 * creating browser history loops (uses <Navigate replace>).
 */

import { expect, test } from '@playwright/test';

test.describe('ODPS Backward-Compat Redirects', () => {
  test.setTimeout(30_000);

  test('/odps redirects to /contracts with spec_type=ODPS filter', async ({ page }) => {
    await page.goto('/odps');
    await page.waitForLoadState('domcontentloaded');

    // Should redirect to contracts list with ODPS filter
    expect(page.url()).toContain('/contracts');
    expect(page.url()).toContain('spec_type=ODPS');
  });

  test('/odps/upload redirects to /contracts/create', async ({ page }) => {
    await page.goto('/odps/upload');
    await page.waitForLoadState('domcontentloaded');

    expect(page.url()).toContain('/contracts/create');
  });

  test('/odps/{id} redirects to /contracts/{id}', async ({ page }) => {
    const fakeId = '00000000-0000-0000-0000-000000000001';
    await page.goto(`/odps/${fakeId}`);
    await page.waitForLoadState('domcontentloaded');

    expect(page.url()).toContain(`/contracts/${fakeId}`);
  });

  test('browser back after /odps redirect does not loop', async ({ page }) => {
    // Start at home
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Navigate to /odps (redirects to /contracts)
    await page.goto('/odps');
    await page.waitForURL(/\/contracts/, { timeout: 10_000 });

    // Go back — should return to home, not /odps
    await page.goBack();
    await page.waitForLoadState('domcontentloaded');

    // Should be back at home, not stuck in redirect loop
    expect(page.url()).not.toContain('/odps');
  });
});
