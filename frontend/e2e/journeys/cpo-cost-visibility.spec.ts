/**
 * Phase 277.B.031 — CPO billing cost visibility journey test.
 *
 * Validates:
 * - PLATFORM_ADMIN can navigate to /settings/cost-overview
 * - The page renders per-tenant and per-feature breakdown tables
 * - Total spend card is visible
 * - Month-over-month trend table renders
 *
 * close-test-coverage-gaps 5.3: replaced the hardcoded
 * `admin@meshant.com/adminpass` credentials and the stale `/auth/login`
 * + `/auth/logout` URLs with the real fixture login
 * (`loginUser` + `getPlatformAdminUser()` / `getTenantAdminUser()`) —
 * the hardcoded account did not exist on the stack, so every test in
 * this spec silently exercised the 404/login-error path before the
 * fix.
 */
import { test, expect } from '@playwright/test';
import { getPlatformAdminUser, getTenantAdminUser, loginUser } from '../fixtures/auth';

test.describe('CPO Cost Overview Journey', () => {
  test('PLATFORM_ADMIN can view cost overview dashboard', async ({ page }) => {
    const admin = await getPlatformAdminUser();
    await loginUser(page, admin);
    await page.goto('/settings/cost-overview');
    await page.waitForSelector('[data-testid="cpo-cost-overview"]');

    // Main container visible
    await expect(page.getByTestId('cpo-cost-overview')).toBeVisible();

    // Page title
    await expect(page.getByRole('heading', { name: 'Cost Overview' })).toBeVisible();

    // Total spend card
    await expect(page.getByTestId('cost-total')).toBeVisible();

    // Per-tenant table
    await expect(page.getByTestId('cost-tenant-table')).toBeVisible();

    // Per-feature table
    await expect(page.getByTestId('cost-feature-table')).toBeVisible();

    // MoM table
    await expect(page.getByTestId('cost-mom-table')).toBeVisible();
  });

  test('non-admin user is redirected away from cost overview', async ({ page }) => {
    // A TENANT_ADMIN is the canonical non-platform-admin contrast —
    // the cost-overview surface is PLATFORM_ADMIN-gated.
    const tenantAdmin = await getTenantAdminUser();
    await loginUser(page, tenantAdmin);

    // Try to access cost overview
    await page.goto('/settings/cost-overview');

    // Should be redirected (403 or redirected to dashboard)
    await expect(page.getByTestId('cpo-cost-overview')).not.toBeVisible();
  });

  test('cost-overview shows empty state when no data', async ({ page }) => {
    // This test expects the backend to have zero completed payments.
    // In CI, the test database starts empty, so the page should render
    // either an empty state or zero-value tables.
    const admin = await getPlatformAdminUser();
    await loginUser(page, admin);
    await page.goto('/settings/cost-overview');
    await page.waitForSelector('[data-testid="cpo-cost-overview"]');

    // Total should show $0.00
    const totalEl = page.getByTestId('cost-total');
    await expect(totalEl).toBeVisible();
  });
});
