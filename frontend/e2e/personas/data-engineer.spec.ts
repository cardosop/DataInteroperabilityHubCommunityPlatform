/**
 * Persona Aggregator: Data Engineer
 * Imports and runs all DE journey specs (JOURNEY-DE-001 through DE-014).
 * Run: npm run test:e2e -- e2e/personas/data-engineer.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

import '../journeys/de/JOURNEY-DE-001.spec';
import '../journeys/de/JOURNEY-DE-002.spec';
import '../journeys/de/JOURNEY-DE-003.spec';
import '../journeys/de/JOURNEY-DE-004.spec';
import '../journeys/de/JOURNEY-DE-005.spec';
import '../journeys/de/JOURNEY-DE-006.spec';
import '../journeys/de/JOURNEY-DE-007.spec';
import '../journeys/de/JOURNEY-DE-008.spec';
import '../journeys/de/JOURNEY-DE-009.spec';
import '../journeys/de/JOURNEY-DE-010.spec';
import '../journeys/de/JOURNEY-DE-011.spec';
import '../journeys/de/JOURNEY-DE-012.spec';
import '../journeys/de/JOURNEY-DE-013.spec';
import '../journeys/de/JOURNEY-DE-014.spec';

import { test, expect } from '@playwright/test';
import { waitForAppMainReady, waitForRoleGuardResolved } from '../fixtures/helpers';
import { loginAsPersona, getTestUser } from '../fixtures/auth';

test.describe('Persona RBAC: Data Engineer', () => {
  test.setTimeout(120000);

  test('DE can access /contracts', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/contracts');
    await waitForAppMainReady(page);
    expect(page.url()).toContain('/contracts');
    await expect(page.locator('.app-main')).toBeVisible();
    await expect(page.locator('.error-display')).not.toBeVisible({ timeout: 2000 });
  });

  test('DE sees scheduled-ingestion gated in MVP mode', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/scheduled-ingestions');
    await waitForAppMainReady(page);
    // Scheduled ingestion is MVP-gated — expect unavailable/coming-soon page
    const url = page.url();
    const hasUnavailable = (await page.locator('.unavailable-page').count()) > 0;
    const isComingSoon = url.includes('/coming-soon') || url.includes('/unavailable');
    expect(
      hasUnavailable || isComingSoon,
      `Expected MVP-gated page (unavailable/coming-soon) but got ${url}`,
    ).toBe(true);
  });

  test('DE cannot access /admin', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/admin');
    await page.waitForLoadState('domcontentloaded');
    const resolvedPath = await waitForRoleGuardResolved(page, { forbiddenPathPrefix: '/admin' });
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
