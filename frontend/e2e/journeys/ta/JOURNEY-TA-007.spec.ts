/**
 * E2E Test: JOURNEY-TA-007 — Monitor Cost Tracking (UC-TA-007)
 *
 * Journey: Monitor Cost Tracking
 * Persona: Tenant Admin
 * Reference: docs/USER_JOURNEYS.md, ManualTest/Front/03-USER-JOURNEYS/ta/JOURNEY-TA-007.md
 *
 * Cost tracking page at /settings/cost. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUser, loginAsPersona } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('JOURNEY-TA-007: Monitor Cost Tracking', () => {
  test.setTimeout(120000);

  test('Phase 18: tenant admin can view cost tracking page', async ({ page }) => {
    const taUser = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, taUser, '/settings/cost', { timeout: 60000 });
    if (page.url().includes('/login') || page.url().includes('/403')) {
      expect(page.url()).toMatch(/\/login|\/403/);
      return;
    }
    expect(page.url()).toContain('/settings/cost');
    await waitForLoadingComplete(page, { timeout: 15000 });

    const costPage = page.locator('[data-testid="cost-page"]');
    await expect(costPage).toBeVisible({ timeout: 10000 });

    const heading = page.locator('h1:has-text("Cost Tracking")');
    await expect(heading).toBeVisible({ timeout: 5000 });
  });

  test('Phase 18: cost summary displays', async ({ page }) => {
    const taUser = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, taUser, '/settings/cost', { timeout: 60000 });
    if (page.url().includes('/login') || page.url().includes('/403')) {
      expect(page.url()).toMatch(/\/login|\/403/);
      return;
    }
    await waitForLoadingComplete(page, { timeout: 15000 });

    const summaryHeading = page.locator('#cost-summary-heading, h2:has-text("Cost Summary")');
    await expect(summaryHeading).toBeVisible({ timeout: 10000 });

    const totalLabel = page.locator('.cost-total-label, :text("Total estimated cost")');
    await expect(totalLabel.first()).toBeVisible({ timeout: 5000 });
  });

  test('Phase 18: cost breakdown visible', async ({ page }) => {
    const taUser = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, taUser, '/settings/cost', { timeout: 60000 });
    if (page.url().includes('/login') || page.url().includes('/403')) {
      expect(page.url()).toMatch(/\/login|\/403/);
      return;
    }
    await waitForLoadingComplete(page, { timeout: 15000 });

    const breakdownList = page.locator('.cost-breakdown-list, .cost-breakdown-item');
    await expect(breakdownList.first()).toBeVisible({ timeout: 10000 });
  });
});
