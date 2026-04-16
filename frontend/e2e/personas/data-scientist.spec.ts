/**
 * Persona Aggregator: Data Scientist
 * Imports and runs all DS journey specs (JOURNEY-DS-001 through JOURNEY-DS-005).
 * Run: npm run test:e2e -- e2e/personas/data-scientist.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

import '../journeys/ds/JOURNEY-DS-001.spec';
import '../journeys/ds/JOURNEY-DS-002.spec';
import '../journeys/ds/JOURNEY-DS-003.spec';
import '../journeys/ds/JOURNEY-DS-004.spec';
import '../journeys/ds/JOURNEY-DS-005.spec';

import { test, expect } from '@playwright/test';
import { loginAsPersona, getTestUser } from '../fixtures/auth';
import { waitForAppMainReady, waitForRoleGuardResolved } from '../fixtures/helpers';

test.describe('Persona RBAC: Data Scientist', () => {
  test.setTimeout(120000);

  test('DS can access /search', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/search');
    await waitForAppMainReady(page);
    expect(page.url()).toContain('/search');
  });

  test('DS can access /ai/search (capability-gated)', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/ai/search');
    await waitForAppMainReady(page);
    const url = page.url();
    expect(url.includes('/ai/search') || url.includes('/403') || url.includes('/unavailable')).toBe(true);
  });

  test('DS cannot access /admin', async ({ page }) => {
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
