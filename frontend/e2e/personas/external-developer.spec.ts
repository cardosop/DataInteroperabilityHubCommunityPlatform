/**
 * Persona Aggregator: External Developer
 * Imports and runs all DEV journey specs (JOURNEY-DEV-001 through DEV-009).
 * Run: npm run test:e2e -- e2e/personas/external-developer.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

import '../journeys/dev/JOURNEY-DEV-001.spec';
import '../journeys/dev/JOURNEY-DEV-002.spec';
import '../journeys/dev/JOURNEY-DEV-003.spec';
import '../journeys/dev/JOURNEY-DEV-004.spec';
import '../journeys/dev/JOURNEY-DEV-005.spec';
import '../journeys/dev/JOURNEY-DEV-006.spec';
import '../journeys/dev/JOURNEY-DEV-007.spec';
import '../journeys/dev/JOURNEY-DEV-008.spec';
import '../journeys/dev/JOURNEY-DEV-009.spec';

import { test, expect } from '@playwright/test';
import { loginAsPersona, getExternalDeveloperUser } from '../fixtures/auth';
import { waitForAppMainReady, waitForRoleGuardResolved } from '../fixtures/helpers';

test.describe('Persona RBAC: External Developer', () => {
  test.setTimeout(120000);

  test('DEV can access /developer', async ({ page }) => {
    await loginAsPersona(page, getExternalDeveloperUser);
    await page.goto('/developer');
    await waitForAppMainReady(page);
    const url = page.url();
    expect(url.includes('/developer') || url.includes('/baas')).toBe(true);
  });

  test('DEV can access /baas', async ({ page }) => {
    await loginAsPersona(page, getExternalDeveloperUser);
    await page.goto('/baas');
    await waitForAppMainReady(page);
    const url = page.url();
    expect(url.includes('/baas') || url.includes('/developer')).toBe(true);
  });

  test('DEV cannot access /admin', async ({ page }) => {
    await loginAsPersona(page, getExternalDeveloperUser);
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
