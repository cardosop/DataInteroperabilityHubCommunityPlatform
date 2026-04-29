/**
 * Persona Aggregator: Visitor / Prospect
 * Imports and runs all auth journey specs (JOURNEY-AUTH-001 through JOURNEY-AUTH-004).
 * Per E2E_FULL_COVERAGE_PLAN: Visitor/Prospect persona (4 auth journeys).
 * Run: npm run test:e2e -- e2e/personas/visitor.spec.ts
 * No mocks/stubs; real backend only.
 */

import '../journeys/auth/JOURNEY-AUTH-001.spec';
import '../journeys/auth/JOURNEY-AUTH-002.spec';
import '../journeys/auth/JOURNEY-AUTH-003.spec';
import '../journeys/auth/JOURNEY-AUTH-004.spec';

import { test, expect } from '@playwright/test';
import { clearAuthStorage, gotoWithRetry } from '../fixtures/auth';

test.describe('Persona RBAC: Visitor (Unauthenticated) @critical', () => {
  test.setTimeout(60000);

  test('unauthenticated user is redirected to login from /assets', async ({ page }) => {
    // RootRoute (frontend/src/app/routes/RootRoute.tsx) renders <Navigate to="/login">
    // when isAuthenticated is false for any non-root path, including /assets.
    await clearAuthStorage(page);
    // gotoWithRetry — Wi-Fi/VPN net::ERR_NETWORK_CHANGED retry. Cycle-2026-04-29 flake fix:
    // first attempt failed with `page.goto: net::ERR_NETWORK_CHANGED at /assets`, retry passed.
    await gotoWithRetry(page, '/assets');
    // Wait specifically for /login — do NOT include the source path in the regex
    // (waitForURL would match the initial URL and return without waiting for the redirect).
    await page.waitForURL(/\/login(\?|$|\/)/, { timeout: 15000 });
    expect(page.url()).toMatch(/\/login(\?|$|\/)/);
  });

  test('unauthenticated user is redirected to login from /admin', async ({ page }) => {
    // /admin is wrapped in <ProtectedRoute requiredRole={['TENANT_ADMIN','PLATFORM_ADMIN']}>.
    // For unauthenticated users, ProtectedRoute also redirects to /login (the role check
    // only fires for authenticated users; unauthenticated users hit the !isAuthenticated branch).
    await clearAuthStorage(page);
    await gotoWithRetry(page, '/admin');
    // Wait for /login (or /403 if the app's behavior changes to render forbidden in-place).
    // Critically, exclude /admin from the regex so waitForURL actually waits.
    await page.waitForURL(/\/(login|403)(\?|$|\/)/, { timeout: 15000 });
    expect(page.url()).toMatch(/\/(login|403)(\?|$|\/)/);
  });
});
