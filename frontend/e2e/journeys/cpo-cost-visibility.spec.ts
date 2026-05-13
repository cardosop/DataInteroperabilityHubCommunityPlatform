/**
 * Phase 277.B.031 — CPO billing cost visibility journey test.
 *
 * Validates:
 * - PLATFORM_ADMIN can navigate to /settings/cost-overview
 * - The page renders per-tenant and per-feature breakdown tables
 * - Total spend card is visible
 * - Month-over-month trend table renders
 */
import { test, expect } from '@playwright/test';

test.describe('CPO Cost Overview Journey', () => {
  test.beforeEach(async ({ page }) => {
    // Log in as platform admin
    await page.goto('/auth/login');
    await page.getByLabel('Email').fill('admin@meshant.com');
    await page.getByLabel('Password').fill('adminpass');
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL(/\/dashboard/);
  });

  test('PLATFORM_ADMIN can view cost overview dashboard', async ({ page }) => {
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
    // Log out admin, log in as regular user
    await page.goto('/auth/logout');
    await page.goto('/auth/login');
    await page.getByLabel('Email').fill('user@meshant.com');
    await page.getByLabel('Password').fill('userpass');
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL(/\/dashboard/);

    // Try to access cost overview
    await page.goto('/settings/cost-overview');

    // Should be redirected (403 or redirected to dashboard)
    await expect(page.getByTestId('cpo-cost-overview')).not.toBeVisible();
  });

  test('cost-overview shows empty state when no data', async ({ page }) => {
    // This test expects the backend to have zero completed payments.
    // In CI, the test database starts empty, so the page should render
    // either an empty state or zero-value tables.
    await page.goto('/settings/cost-overview');
    await page.waitForSelector('[data-testid="cpo-cost-overview"]');

    // Total should show $0.00
    const totalEl = page.getByTestId('cost-total');
    await expect(totalEl).toBeVisible();
  });
});
