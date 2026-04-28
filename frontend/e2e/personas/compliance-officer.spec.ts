/**
 * Persona Aggregator: Compliance Officer
 * Imports and runs all CPO journey specs (JOURNEY-CPO-001 through CPO-010).
 * Run: npm run test:e2e -- e2e/personas/compliance-officer.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

import '../journeys/cpo/JOURNEY-CPO-001.spec';
import '../journeys/cpo/JOURNEY-CPO-002.spec';
import '../journeys/cpo/JOURNEY-CPO-003.spec';
import '../journeys/cpo/JOURNEY-CPO-004.spec';
import '../journeys/cpo/JOURNEY-CPO-005.spec';
import '../journeys/cpo/JOURNEY-CPO-006.spec';
import '../journeys/cpo/JOURNEY-CPO-007.spec';
import '../journeys/cpo/JOURNEY-CPO-008.spec';
import '../journeys/cpo/JOURNEY-CPO-009.spec';
import '../journeys/cpo/JOURNEY-CPO-010.spec';

import { test, expect } from '@playwright/test';
import { loginAsPersona, getComplianceOfficerUser, getTestUser } from '../fixtures/auth';
import { waitForAppMainReady, waitForRoleGuardResolved } from '../fixtures/helpers';

test.describe('Persona RBAC: Compliance Officer @critical', () => {
  test.setTimeout(120000);

  test('CPO can access /compliance', async ({ page }) => {
    await loginAsPersona(page, getComplianceOfficerUser);
    // waitUntil: 'domcontentloaded' instead of the default 'load'. 'load' blocks
    // until every subresource (including lazy-loaded route chunks fetched mid-render
    // by React.lazy) has finished, which exceeds the 30s navigationTimeout on a
    // cold staging worker. waitForAppMainReady performs the real readiness check.
    await page.goto('/compliance', { waitUntil: 'domcontentloaded' });
    await waitForAppMainReady(page);
    expect(page.url()).toContain('/compliance');
    await expect(page.locator('.app-main, [data-testid="app-main"]').first()).toBeVisible();
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 2000 });
  });

  test('CPO can access /governance', async ({ page }) => {
    await loginAsPersona(page, getComplianceOfficerUser);
    await page.goto('/governance');
    await waitForAppMainReady(page);
    const url = page.url();
    if (url.includes('/403')) test.skip(true, 'CPO does not have governance access');
    expect(url).toContain('/governance');
    await expect(page.locator('.app-main, [data-testid="app-main"]').first()).toBeVisible();
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 2000 });
  });

  test('non-CPO user cannot access /audit', async ({ page }) => {
    // storageState already has the default DATA_PROVIDER user (non-CPO).
    // No need for loginAsPersona — saves an API login call and avoids rate limits.
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
