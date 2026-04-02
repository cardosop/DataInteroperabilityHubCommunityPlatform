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
import { clearAuthStorage } from '../fixtures/auth';

test.describe('Persona RBAC: Visitor (Unauthenticated)', () => {
  test.setTimeout(60000);

  test('unauthenticated user is redirected to login from /assets', async ({ page }) => {
    await clearAuthStorage(page);
    await page.goto('/assets');
    await page.waitForURL(/\/(login|assets)/, { timeout: 15000 });
    const url = page.url();
    const onLogin = url.includes('/login');
    const hasLoginPrompt = url.includes('/assets') && (await page.locator('input#email, [href*="/login"], text=Sign in').count()) > 0;
    expect(onLogin || hasLoginPrompt).toBe(true);
  });

  test('unauthenticated user is redirected to login from /admin', async ({ page }) => {
    await clearAuthStorage(page);
    await page.goto('/admin');
    await page.waitForURL(/\/(login|admin|403)/, { timeout: 15000 });
    const url = page.url();
    expect(url.includes('/login') || url.includes('/403')).toBe(true);
  });
});
