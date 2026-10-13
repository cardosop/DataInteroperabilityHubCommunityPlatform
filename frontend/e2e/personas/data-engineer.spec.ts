/**
 * Persona Aggregator: Data Engineer
 * Imports and runs all DE journey specs (JOURNEY-DE-001 through DE-014).
 * Run: npm run test:e2e -- e2e/personas/data-engineer.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

// Core-only mode (E2E_CORE_ONLY=1): the imported journey specs are FULL-mode
// journeys; the core subset runs the persona's own RBAC tests below instead.
if (process.env.E2E_CORE_ONLY !== '1') {
  await import('../journeys/de/JOURNEY-DE-001.spec');
  await import('../journeys/de/JOURNEY-DE-002.spec');
  await import('../journeys/de/JOURNEY-DE-003.spec');
  await import('../journeys/de/JOURNEY-DE-004.spec');
  await import('../journeys/de/JOURNEY-DE-005.spec');
  await import('../journeys/de/JOURNEY-DE-006.spec');
  await import('../journeys/de/JOURNEY-DE-007.spec');
  await import('../journeys/de/JOURNEY-DE-008.spec');
  await import('../journeys/de/JOURNEY-DE-009.spec');
  await import('../journeys/de/JOURNEY-DE-010.spec');
  await import('../journeys/de/JOURNEY-DE-011.spec');
  await import('../journeys/de/JOURNEY-DE-012.spec');
  await import('../journeys/de/JOURNEY-DE-013.spec');
  await import('../journeys/de/JOURNEY-DE-014.spec');
  // close-test-coverage-gaps 6.3 — JOURNEY-DE-015 was orphaned (not run
  // by any persona aggregator).
  await import('../journeys/de/JOURNEY-DE-015.spec');
  await import('../journeys/de/JOURNEY-DB-001.spec');
  await import('../journeys/de/JOURNEY-DB-005.spec');
  await import('../journeys/de/JOURNEY-DB-006.spec');
  await import('../journeys/de/JOURNEY-DB-007.spec');
  await import('../journeys/de/JOURNEY-DB-010.spec');
  await import('../journeys/de/JOURNEY-DB-011.spec');
  await import('../journeys/de/JOURNEY-DB-013.spec');
  await import('../journeys/de/JOURNEY-DB-014.spec');
  await import('../journeys/de/JOURNEY-DB-017.spec');
  await import('../journeys/de/JOURNEY-DB-018.spec');
  // 276.B.105 remediation — the real scheduled ingestion/export journeys
  // replace the former deferred stub (scheduled-jobs.spec.ts, removed).
  await import('../journeys/de/JOURNEY-INGESTION-001.spec');
  await import('../journeys/de/JOURNEY-INGESTION-003.spec');
  await import('../journeys/de/JOURNEY-EXPORT-001.spec');

}

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

  test('DE sees scheduled-ingestion mode-aware: serves in core-only, gated in MVP', async ({ page }) => {
    // 313.H.4.3 — mode-aware assertion instead of a core-only skip: MVP
    // gating is a release control that only exists in MVP-mode deploys.
    // In core-only deployments (E2E_CORE_ONLY=1) the route must SERVE;
    // in the standard MVP e2e run it must be gated.
    await loginAsPersona(page, getTestUser);
    // gotoWithRetry — Wi-Fi/VPN net::ERR_NETWORK_CHANGED retry. Cycle-2026-04-29 flake fix:
    // first attempt failed with `page.goto: net::ERR_NETWORK_CHANGED at /scheduled-ingestions`,
    // retry passed. The bare `page.goto` propagated the transient Chromium net error; the
    // wrapper's regex (auth.ts isConnectionError) matches it and the next attempt succeeds.
    await gotoWithRetry(page, '/scheduled-ingestions');
    await waitForAppMainReady(page);
    const url = page.url();
    const hasUnavailable = (await page.locator('.unavailable-page, [data-testid="unavailable-page"]').first().count()) > 0;
    const isGated = hasUnavailable || url.includes('/coming-soon') || url.includes('/unavailable');

    if (process.env.E2E_CORE_ONLY === '1') {
      // Core-only: no MVP gate — the scheduled-ingestion list must render.
      expect(
        isGated,
        `Expected /scheduled-ingestions to serve in core-only but got ${url}`,
      ).toBe(false);
      await expect(
        page.locator('.app-main, [data-testid="app-main"]').first(),
      ).toBeVisible();
      return;
    }

    // MVP-mode deploy: the route is gated — expect unavailable/coming-soon.
    expect(
      isGated,
      `Expected MVP-gated page (unavailable/coming-soon) but got ${url}`,
    ).toBe(true);
  });

  test('DE cannot access /admin', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await gotoWithRetry(page, '/admin');
    await page.waitForLoadState('domcontentloaded');
    const resolvedPath = await waitForRoleGuardResolved(page, { forbiddenPathPrefix: '/admin' });
    if (resolvedPath.includes('/login')) {
      test.skip(resolvedPath.includes('/login'), 'Auth session expired — not an RBAC result');
      return;
    }
    expect(
      resolvedPath.includes('/403') ||
        resolvedPath.startsWith('/coming-soon') ||
        resolvedPath.startsWith('/unavailable')
    ).toBe(true);
  });
});
