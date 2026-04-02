/**
 * Persona Aggregator: Tenant Admin
 * Imports and runs all TA journey specs (JOURNEY-TA-001 through TA-008)
 * and JOURNEY-MP-001 (Connect to External Marketplace; per MARKETPLACE_USER_JOURNEYS.md MP-001 persona is DPO+TA).
 * Run: npm run test:e2e -- e2e/personas/tenant-admin.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

import '../journeys/ta/JOURNEY-TA-001.spec';
import '../journeys/ta/JOURNEY-TA-002.spec';
import '../journeys/ta/JOURNEY-TA-003.spec';
import '../journeys/ta/JOURNEY-TA-004.spec';
import '../journeys/ta/JOURNEY-TA-005.spec';
import '../journeys/ta/JOURNEY-TA-006.spec';
import '../journeys/ta/JOURNEY-TA-007.spec';
import '../journeys/ta/JOURNEY-TA-008.spec';
import '../journeys/marketplace/JOURNEY-MP-001.spec';

import { test, expect } from '@playwright/test';
import { waitForAppMainReady, waitForRoleGuardResolved } from '../fixtures/helpers';
import { loginAsPersona, getTenantAdminUser } from '../fixtures/auth';

test.describe('Persona RBAC: Tenant Admin', () => {
  test.setTimeout(120000);

  test('TA can access /admin', async ({ page }) => {
    await loginAsPersona(page, getTenantAdminUser);
    await page.goto('/admin');
    await waitForAppMainReady(page);
    const url = page.url();
    expect(url.includes('/admin') || url.includes('/settings')).toBe(true);
    await expect(page.locator('.app-main')).toBeVisible();
    await expect(page.locator('.error-display')).not.toBeVisible({ timeout: 2000 });
  });

  test('TA can access /settings/tenant', async ({ page }) => {
    await loginAsPersona(page, getTenantAdminUser);
    await page.goto('/settings/tenant');
    await waitForAppMainReady(page);
    expect(page.url()).toContain('/settings');
    await expect(page.locator('.app-main')).toBeVisible();
    await expect(page.locator('.error-display')).not.toBeVisible({ timeout: 2000 });
  });

  test('TA cannot access /audit (auditor-only route)', async ({ page }) => {
    await loginAsPersona(page, getTenantAdminUser);
    await page.goto('/audit');
    await page.waitForLoadState('domcontentloaded');
    await waitForRoleGuardResolved(page, { forbiddenPathPrefix: '/audit' });
    const path = new URL(page.url()).pathname;
    expect(
      path.includes('/403') ||
        path.includes('/login') ||
        path.startsWith('/coming-soon') ||
        path.startsWith('/unavailable')
    ).toBe(true);
  });
});
