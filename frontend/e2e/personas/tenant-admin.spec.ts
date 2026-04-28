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

test.describe('Persona RBAC: Tenant Admin @critical', () => {
  test.setTimeout(120000);

  // Note: TENANT_ADMIN role assignment is performed by the Django management
  // command `ensure_e2e_user_roles`, which the deploy pipeline runs (and which
  // can be re-run via `kubectl exec ...`). getTenantAdminUser() throws with a
  // clear remediation message if the user is missing — no need for a blanket
  // skipIfRemoteApi here.

  test('TA can access /admin', async ({ page }) => {
    await loginAsPersona(page, getTenantAdminUser);
    await page.goto('/admin');
    await waitForAppMainReady(page);
    const url = page.url();
    expect(url.includes('/admin') || url.includes('/settings')).toBe(true);
    await expect(page.locator('.app-main, [data-testid="app-main"]').first()).toBeVisible();
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 2000 });
  });

  test('TA can access /settings/tenant', async ({ page }) => {
    await loginAsPersona(page, getTenantAdminUser);
    await page.goto('/settings/tenant');
    await waitForAppMainReady(page);
    expect(page.url()).toContain('/settings');
    await expect(page.locator('.app-main, [data-testid="app-main"]').first()).toBeVisible();
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 2000 });
  });

  test('TA cannot access /audit (auditor-only route)', async ({ page }) => {
    await loginAsPersona(page, getTenantAdminUser);
    await page.goto('/audit');
    await page.waitForLoadState('domcontentloaded');
    const resolvedPath = await waitForRoleGuardResolved(page, { forbiddenPathPrefix: '/audit' });
    if (resolvedPath.includes('/login')) {
      test.skip(true, 'Auth session expired — not an RBAC result');
      return;
    }
    expect(
      resolvedPath.includes('/403') ||
        resolvedPath.startsWith('/coming-soon') ||
        resolvedPath.startsWith('/unavailable')
    ).toBe(true);
  });
});
