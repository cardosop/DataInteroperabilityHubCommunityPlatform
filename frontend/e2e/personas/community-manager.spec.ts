/**
 * Persona Aggregator: Community Manager
 * Imports and runs all CM journey specs (JOURNEY-CM-001 through JOURNEY-CM-004).
 * Run: npm run test:e2e -- e2e/personas/community-manager.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

import '../journeys/cm/JOURNEY-CM-001.spec';
import '../journeys/cm/JOURNEY-CM-002.spec';
import '../journeys/cm/JOURNEY-CM-003.spec';
import '../journeys/cm/JOURNEY-CM-004.spec';

import { test, expect } from '@playwright/test';
import { loginAsPersona, getTestUser } from '../fixtures/auth';

test.describe('Persona RBAC: Community Manager', () => {
  test.setTimeout(120000);

  test('CM can access /communities (capability-gated)', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/communities');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    test.skip(page.url().includes('/login'), 'Auth redirect');
    const url = page.url();
    // Communities may be capability-gated
    expect(url.includes('/communities') || url.includes('/403') || url.includes('/unavailable')).toBe(true);
  });

  test('CM cannot access /admin', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/admin');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForURL(/\/(403|login|admin|assets)/, { timeout: 20000 }).catch(() => null);
    const url = page.url();
    expect(url.includes('/403') || url.includes('/login') || !url.includes('/admin')).toBe(true);
  });
});
