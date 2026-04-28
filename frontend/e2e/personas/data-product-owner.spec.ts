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
import { waitForAppMainReady, waitForRoleGuardResolved } from '../fixtures/helpers';

test.describe('Persona RBAC: Data Product Owner @critical', () => {
  test.setTimeout(120000);

  test('DPO can access /assets', async ({ page }) => {
    await loginAsPersona(page, getTestUser); // getTestUser is DATA_PROVIDER (DPO)
    await page.goto('/assets');
    await waitForAppMainReady(page);
    expect(page.url()).toContain('/assets');
    await expect(page.locator('.app-main, [data-testid="app-main"]').first()).toBeVisible();
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 2000 });
    // Assert actual asset content rendered (not just app shell)
    const hasContent = page.locator(
      '.asset-list-page, [data-testid="asset-list-page"], .asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"]',
    );
    await expect(hasContent.first()).toBeVisible({ timeout: 30000 });
  });

  test('DPO can access /contracts', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/contracts');
    await waitForAppMainReady(page);
    expect(page.url()).toContain('/contracts');
    await expect(page.locator('.app-main, [data-testid="app-main"]').first()).toBeVisible();
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 2000 });
    // Assert actual contract content rendered (not just app shell)
    const hasContent = page.locator(
      '.contract-list-page, [data-testid="contract-list-page"], .contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"]',
    );
    await expect(hasContent.first()).toBeVisible({ timeout: 30000 });
  });

  test('DPO cannot access /admin (admin-only route)', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/admin');
    await page.waitForLoadState('domcontentloaded');
    const resolvedPath = await waitForRoleGuardResolved(page, { forbiddenPathPrefix: '/admin' });
    if (resolvedPath.includes('/login')) {
      test.skip(true, 'Auth session expired — not an RBAC result');
      return;
    }
    expect(
      resolvedPath.includes('/403') ||
        resolvedPath.startsWith('/coming-soon') ||
        resolvedPath.startsWith('/unavailable')
    ).toBe(true);
  });
});
