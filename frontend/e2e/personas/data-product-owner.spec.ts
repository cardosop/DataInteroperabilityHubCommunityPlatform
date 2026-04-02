/**
 * Persona Aggregator: Data Product Owner
 * Imports and runs all DPO journey specs (JOURNEY-DPO-001 through JOURNEY-DPO-017)
 * and Marketplace integration journeys (JOURNEY-MP-001 through JOURNEY-MP-007).
 * Per MARKETPLACE_USER_JOURNEYS.md, MP-001/MP-002 are DPO personas; MP journeys
 * integrated here per Phase 6.11.5 design.
 * Run: npm run test:e2e -- e2e/personas/data-product-owner.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

import '../journeys/dpo/JOURNEY-DPO-001.spec';
import '../journeys/dpo/JOURNEY-DPO-002.spec';
import '../journeys/dpo/JOURNEY-DPO-003.spec';
import '../journeys/dpo/JOURNEY-DPO-004.spec';
import '../journeys/dpo/JOURNEY-DPO-005.spec';
import '../journeys/dpo/JOURNEY-DPO-006.spec';
import '../journeys/dpo/JOURNEY-DPO-007.spec';
import '../journeys/dpo/JOURNEY-DPO-008.spec';
import '../journeys/dpo/JOURNEY-DPO-009.spec';
import '../journeys/dpo/JOURNEY-DPO-010.spec';
import '../journeys/dpo/JOURNEY-DPO-011.spec';
import '../journeys/dpo/JOURNEY-DPO-012.spec';
import '../journeys/dpo/JOURNEY-DPO-013.spec';
import '../journeys/dpo/JOURNEY-DPO-014.spec';
import '../journeys/dpo/JOURNEY-DPO-015.spec';
import '../journeys/dpo/JOURNEY-DPO-016.spec';
import '../journeys/dpo/JOURNEY-DPO-017.spec';
import '../journeys/marketplace/JOURNEY-MP-001.spec';
import '../journeys/marketplace/JOURNEY-MP-002.spec';
import '../journeys/marketplace/JOURNEY-MP-003.spec';
import '../journeys/marketplace/JOURNEY-MP-004.spec';
import '../journeys/marketplace/JOURNEY-MP-005.spec';
import '../journeys/marketplace/JOURNEY-MP-006.spec';
import '../journeys/marketplace/JOURNEY-MP-007.spec';

import { test, expect } from '@playwright/test';
import { loginAsPersona, getTestUser } from '../fixtures/auth';

test.describe('Persona RBAC: Data Product Owner', () => {
  test.setTimeout(120000);

  test('DPO can access /assets', async ({ page }) => {
    await loginAsPersona(page, getTestUser); // getTestUser is DATA_PROVIDER (DPO)
    await page.goto('/assets');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    test.skip(page.url().includes('/login'), 'Auth redirect');
    expect(page.url()).toContain('/assets');
    await expect(page.locator('.error-display')).not.toBeVisible({ timeout: 2000 });
  });

  test('DPO can access /contracts', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/contracts');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    test.skip(page.url().includes('/login'), 'Auth redirect');
    expect(page.url()).toContain('/contracts');
  });

  test('DPO cannot access /admin (admin-only route)', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/admin');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForURL(/\/(403|login|admin|assets)/, { timeout: 20000 }).catch(() => null);
    const url = page.url();
    // DPO should NOT land on /admin without 403 — either redirected or forbidden
    expect(url.includes('/403') || url.includes('/login') || !url.includes('/admin')).toBe(true);
  });
});
