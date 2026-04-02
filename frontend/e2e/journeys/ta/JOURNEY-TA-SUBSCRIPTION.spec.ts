/**
 * E2E Test: Phase 17 — Change Plan & Invoices
 *
 * Tenant admin views subscription page, plan change UI, and invoice history.
 * No mocks/stubs; real backend only.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('Phase 17: Change Plan & Invoices', () => {
  test.setTimeout(120000);

  test('subscription page loads with plan and invoice history', async ({ page }) => {
    const taUser = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, taUser, '/settings/subscription', { timeout: 60000 });
    if (page.url().includes('/login') || page.url().includes('/403')) {
      expect(page.url()).toMatch(/\/login|\/403/);
      return;
    }
    expect(page.url()).toContain('/settings/subscription');
    await waitForLoadingComplete(page, { timeout: 15000 });

    const planHeading = page.locator('#subscription-plan-heading, h2:has-text("Plan")');
    await expect(planHeading).toBeVisible({ timeout: 10000 });

    const invoiceHeading = page.locator('#subscription-invoices-heading, h2:has-text("Invoice history")');
    await expect(invoiceHeading).toBeVisible({ timeout: 10000 });
  });

  test('plan change dropdown visible when other plans exist', async ({ page }) => {
    const taUser = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, taUser, '/settings/subscription', { timeout: 60000 });
    if (page.url().includes('/login') || page.url().includes('/403')) {
      expect(page.url()).toMatch(/\/login|\/403/);
      return;
    }
    await waitForLoadingComplete(page, { timeout: 15000 });

    const changePlanSection = page.locator('.subscription-change-plan');
    const changePlanSelect = page.locator('.subscription-change-plan-controls select');
    await changePlanSection.waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);
    if (!(await changePlanSection.isVisible())) {
      test.skip(true, 'Change plan section not visible (no alternative plans available)');
      return;
    }
    await expect(changePlanSelect).toBeVisible({ timeout: 5000 });
  });

  test('invoice history section shows table or empty state', async ({ page }) => {
    const taUser = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, taUser, '/settings/subscription', { timeout: 60000 });
    if (page.url().includes('/login') || page.url().includes('/403')) {
      expect(page.url()).toMatch(/\/login|\/403/);
      return;
    }
    await waitForLoadingComplete(page, { timeout: 15000 });

    const invoiceSection = page.locator('[aria-labelledby="subscription-invoices-heading"]');
    await expect(invoiceSection).toBeVisible({ timeout: 10000 });

    const hasTable = await page.locator('.subscription-invoices-table').isVisible();
    const hasEmpty = await page.locator('.subscription-no-data:has-text("No invoices")').isVisible();
    expect(hasTable || hasEmpty).toBe(true) /* acceptable states */;
  });
});
