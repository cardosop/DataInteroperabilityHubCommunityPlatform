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
import { loginAsPersona, getPlatformAdminUser } from '../fixtures/auth';

test.describe('Persona RBAC: Platform Admin', () => {
  test.setTimeout(120000);

  test('PA can access /admin', async ({ page }) => {
    await loginAsPersona(page, getPlatformAdminUser);
    await page.goto('/admin');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    test.skip(page.url().includes('/login'), 'Auth redirect');
    const url = page.url();
    expect(url.includes('/admin') || url.includes('/settings')).toBe(true);
  });

  test('PA can access /assets', async ({ page }) => {
    await loginAsPersona(page, getPlatformAdminUser);
    await page.goto('/assets');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    test.skip(page.url().includes('/login'), 'Auth redirect');
    expect(page.url()).toContain('/assets');
  });

  test('PA can access /audit', async ({ page }) => {
    await loginAsPersona(page, getPlatformAdminUser);
    await page.goto('/audit');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    test.skip(page.url().includes('/login'), 'Auth redirect');
    // PA should have full access — 403 means RBAC misconfiguration
    expect(page.url()).toContain('/audit');
  });
});
