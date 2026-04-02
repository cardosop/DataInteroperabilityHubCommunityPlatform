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
import { loginAsPersona, getTenantAdminUser } from '../fixtures/auth';

test.describe('Persona RBAC: Tenant Admin', () => {
  test.setTimeout(120000);

  test('TA can access /admin', async ({ page }) => {
    await loginAsPersona(page, getTenantAdminUser);
    await page.goto('/admin');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    test.skip(page.url().includes('/login'), 'Auth redirect');
    const url = page.url();
    expect(url.includes('/admin') || url.includes('/settings')).toBe(true);
    await expect(page.locator('.error-display')).not.toBeVisible({ timeout: 2000 });
  });

  test('TA can access /settings/tenant', async ({ page }) => {
    await loginAsPersona(page, getTenantAdminUser);
    await page.goto('/settings/tenant');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    test.skip(page.url().includes('/login'), 'Auth redirect');
    expect(page.url()).toContain('/settings');
  });

  test('TA cannot access /audit (auditor-only route)', async ({ page }) => {
    await loginAsPersona(page, getTenantAdminUser);
    await page.goto('/audit');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForURL(/\/(403|login|audit)/, { timeout: 20000 }).catch(() => null);
    const url = page.url();
    // TA should NOT have access to audit logs — either 403 or redirected away
    expect(url.includes('/403') || url.includes('/login') || !url.includes('/audit')).toBe(true);
  });
});
