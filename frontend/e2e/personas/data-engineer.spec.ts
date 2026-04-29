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
import {
  injectTokensBeforeGotoForUser,
  waitForAppMainReady,
  waitForRoleGuardResolved,
} from '../fixtures/helpers';
import { loginAsPersona, getTestUser, gotoWithRetry } from '../fixtures/auth';

test.describe('Persona RBAC: Data Engineer @critical', () => {
  test.setTimeout(120000);

  test('DE can access /contracts', async ({ page }) => {
    const user = await getTestUser();
    await loginAsPersona(page, getTestUser);
    // Cycle-2026-04-29 Pattern-B flake fix — `waitForAppMainReady: Redirected
    // to login`. By the time this persona test runs (~mid-suite) the
    // storageState's access_token may already be stale, the loginAsPersona
    // fast-path may have succeeded but a background React Query refetch can
    // 401 between the goto and the readiness check, clearing the in-memory
    // token. Re-inject right before the goto so the SPA's auth-store
    // initialize() reads coherent fresh tokens. Same root-cause + fix as
    // multi-tenancy-isolation:235 / data-quality:235.
    await injectTokensBeforeGotoForUser(page, user);
    // gotoWithRetry — Wi-Fi/VPN net::ERR_NETWORK_CHANGED retry (Fix 27).
    await gotoWithRetry(page, '/contracts');
    await waitForAppMainReady(page);
    expect(page.url()).toContain('/contracts');
    await expect(page.locator('.app-main, [data-testid="app-main"]').first()).toBeVisible();
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 2000 });
  });

  test('DE sees scheduled-ingestion gated in MVP mode', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    // gotoWithRetry — Wi-Fi/VPN net::ERR_NETWORK_CHANGED retry. Cycle-2026-04-29 flake fix:
    // first attempt failed with `page.goto: net::ERR_NETWORK_CHANGED at /scheduled-ingestions`,
    // retry passed. The bare `page.goto` propagated the transient Chromium net error; the
    // wrapper's regex (auth.ts isConnectionError) matches it and the next attempt succeeds.
    await gotoWithRetry(page, '/scheduled-ingestions');
    await waitForAppMainReady(page);
    // Scheduled ingestion is MVP-gated — expect unavailable/coming-soon page
    const url = page.url();
    const hasUnavailable = (await page.locator('.unavailable-page, [data-testid="unavailable-page"]').first().count()) > 0;
    const isComingSoon = url.includes('/coming-soon') || url.includes('/unavailable');
    expect(
      hasUnavailable || isComingSoon,
      `Expected MVP-gated page (unavailable/coming-soon) but got ${url}`,
    ).toBe(true);
  });

  test('DE cannot access /admin', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await gotoWithRetry(page, '/admin');
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
