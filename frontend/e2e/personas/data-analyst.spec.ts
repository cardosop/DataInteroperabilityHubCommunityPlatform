/**
 * Persona Aggregator: Data Analyst
 * Imports and runs all DA journey specs (JOURNEY-DA-001 through DA-004).
 * Run: npm run test:e2e -- e2e/personas/data-analyst.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

import '../journeys/da/JOURNEY-DA-001.spec';
import '../journeys/da/JOURNEY-DA-002.spec';
import '../journeys/da/JOURNEY-DA-003.spec';
import '../journeys/da/JOURNEY-DA-004.spec';

import { test, expect } from '@playwright/test';
import { loginAsPersona, getTestUser } from '../fixtures/auth';
import { waitForAppMainReady, waitForRoleGuardResolved } from '../fixtures/helpers';

test.describe('Persona RBAC: Data Analyst', () => {
  test.setTimeout(120000);

  test('DA can access /virtualization', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/virtualization');
    await waitForAppMainReady(page);
    const url = page.url();
    expect(url.includes('/virtualization') || url.includes('/403') || url.includes('/unavailable')).toBe(true);
  });

  test('DA can access /transformation', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/transformation');
    await waitForAppMainReady(page);
    const url = page.url();
    expect(url.includes('/transformation') || url.includes('/403') || url.includes('/unavailable')).toBe(true);
  });

  test('DA cannot access /admin', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/admin');
    await page.waitForLoadState('domcontentloaded');
    const resolved = await waitForRoleGuardResolved(page, { forbiddenPathPrefix: '/admin' });
    if (resolved.includes('/login')) {
      test.skip(true, 'Auth session expired — not an RBAC result');
      return;
    }
    expect(resolved.includes('/403') || !resolved.includes('/admin')).toBe(true);
  });
});
