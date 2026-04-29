/**
 * Persona Aggregator: Platform Admin
 * Imports and runs all PA/MPA journey specs.
 * Run: npm run test:e2e -- e2e/personas/platform-admin.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

import '../journeys/pa/JOURNEY-PA-001.spec';
import '../journeys/pa/JOURNEY-MPA-001.spec';
import '../journeys/pa/JOURNEY-MPA-002.spec';
import '../journeys/pa/JOURNEY-MPA-003.spec';
import '../journeys/pa/JOURNEY-MPA-004.spec';
import '../journeys/pa/JOURNEY-MPA-005.spec';
import '../journeys/pa/JOURNEY-MPA-006.spec';
import '../journeys/pa/JOURNEY-MPA-007.spec';
import '../journeys/pa/JOURNEY-MPA-008.spec';
import '../journeys/pa/JOURNEY-MPA-009.spec';
import '../journeys/pa/JOURNEY-PA-010.spec';

import { test, expect } from '@playwright/test';
import { loginAsPersona, getPlatformAdminUser, gotoWithRetry } from '../fixtures/auth';
import { injectTokensBeforeGotoForUser, waitForAppMainReady } from '../fixtures/helpers';

test.describe('Persona RBAC: Platform Admin @critical', () => {
  test.setTimeout(120000);

  // Note: PLATFORM_ADMIN role assignment is performed by the Django management
  // command `ensure_e2e_user_roles`, which the deploy pipeline runs (and which
  // can be re-run via `kubectl exec ...`). getPlatformAdminUser() throws with
  // a clear remediation message if the user is missing — no need for a blanket
  // skipIfRemoteApi here.

  test('PA can access /admin', async ({ page }) => {
    await loginAsPersona(page, getPlatformAdminUser);
    await gotoWithRetry(page, '/admin');
    await waitForAppMainReady(page);
    const url = page.url();
    expect(url.includes('/admin') || url.includes('/settings')).toBe(true);
    await expect(page.locator('.app-main, [data-testid="app-main"]').first()).toBeVisible();
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 2000 });
  });

  test('PA can access /assets', async ({ page }) => {
    await loginAsPersona(page, getPlatformAdminUser);
    await gotoWithRetry(page, '/assets');
    await waitForAppMainReady(page);
    expect(page.url()).toContain('/assets');
    await expect(page.locator('.app-main, [data-testid="app-main"]').first()).toBeVisible();
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 2000 });
  });

  test('PA can access /audit', async ({ page }) => {
    const paUser = await getPlatformAdminUser();
    await loginAsPersona(page, getPlatformAdminUser);
    // Cycle-2026-04-29 Pattern-B flake fix — same root cause as
    // data-engineer:30: storageState's access_token is stale mid-suite, a
    // background 401 clears in-memory state, and the next nav redirects to
    // /login. Re-inject before goto.
    await injectTokensBeforeGotoForUser(page, paUser);
    await gotoWithRetry(page, '/audit');
    await waitForAppMainReady(page);
    // PA should have full access — 403 means RBAC misconfiguration
    expect(page.url()).toContain('/audit');
    await expect(page.locator('.app-main, [data-testid="app-main"]').first()).toBeVisible();
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 2000 });
  });

  test('PA can access /settings/tenant (full-privilege role)', async ({ page }) => {
    await loginAsPersona(page, getPlatformAdminUser);
    // gotoWithRetry — Wi-Fi/VPN net::ERR_NETWORK_CHANGED retry. Cycle-2026-04-29 flake fix:
    // first attempt failed with `page.goto: net::ERR_NETWORK_CHANGED at /settings/tenant`,
    // retry passed. The bare `page.goto` propagated the transient Chromium net error;
    // the wrapper's regex (auth.ts isConnectionError) matches and retries with backoff.
    await gotoWithRetry(page, '/settings/tenant');
    await waitForAppMainReady(page);
    expect(page.url()).toContain('/settings');
    await expect(page.locator('.app-main, [data-testid="app-main"]').first()).toBeVisible();
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 2000 });
  });
});
