/**
 * Persona Aggregator: Data Consumer
 * Imports and runs all DC journey specs (JOURNEY-DC-001 through JOURNEY-DC-015).
 * Run: npm run test:e2e -- e2e/personas/data-consumer.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

import '../journeys/dc/JOURNEY-DC-001.spec';
import '../journeys/dc/JOURNEY-DC-002.spec';
import '../journeys/dc/JOURNEY-DC-003.spec';
import '../journeys/dc/JOURNEY-DC-004.spec';
import '../journeys/dc/JOURNEY-DC-005.spec';
import '../journeys/dc/JOURNEY-DC-006.spec';
import '../journeys/dc/JOURNEY-DC-007.spec';
import '../journeys/dc/JOURNEY-DC-008.spec';
import '../journeys/dc/JOURNEY-DC-009.spec';
import '../journeys/dc/JOURNEY-DC-010.spec';
import '../journeys/dc/JOURNEY-DC-011.spec';
import '../journeys/dc/JOURNEY-DC-012.spec';
import '../journeys/dc/JOURNEY-DC-013.spec';
import '../journeys/dc/JOURNEY-DC-014.spec';
import '../journeys/dc/JOURNEY-DC-015.spec';

import { test, expect } from '@playwright/test';
import { waitForAppMainReady, waitForRoleGuardResolved } from '../fixtures/helpers';
import { loginAsPersona, getConsumerTestUser } from '../fixtures/auth';

test.describe('Persona RBAC: Data Consumer', () => {
  test.setTimeout(120000);

  test('DC can access /marketplace', async ({ page }) => {
    await loginAsPersona(page, getConsumerTestUser);
    await page.goto('/marketplace');
    await waitForAppMainReady(page);
    expect(page.url()).toContain('/marketplace');
    await expect(page.locator('.app-main')).toBeVisible();
    await expect(page.locator('.error-display')).not.toBeVisible({ timeout: 2000 });
  });

  test('DC cannot access /admin', async ({ page }) => {
    await loginAsPersona(page, getConsumerTestUser);
    await page.goto('/admin');
    await page.waitForLoadState('domcontentloaded');
    await waitForRoleGuardResolved(page, { forbiddenPathPrefix: '/admin' });
    const path = new URL(page.url()).pathname;
    expect(
      path.includes('/403') ||
        path.includes('/login') ||
        path.startsWith('/coming-soon') ||
        path.startsWith('/unavailable')
    ).toBe(true);
  });
});
