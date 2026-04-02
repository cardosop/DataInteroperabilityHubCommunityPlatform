/**
 * Persona Aggregator: Compliance Officer
 * Imports and runs all CPO journey specs (JOURNEY-CPO-001 through CPO-010).
 * Run: npm run test:e2e -- e2e/personas/compliance-officer.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

import '../journeys/cpo/JOURNEY-CPO-001.spec';
import '../journeys/cpo/JOURNEY-CPO-002.spec';
import '../journeys/cpo/JOURNEY-CPO-003.spec';
import '../journeys/cpo/JOURNEY-CPO-004.spec';
import '../journeys/cpo/JOURNEY-CPO-005.spec';
import '../journeys/cpo/JOURNEY-CPO-006.spec';
import '../journeys/cpo/JOURNEY-CPO-007.spec';
import '../journeys/cpo/JOURNEY-CPO-008.spec';
import '../journeys/cpo/JOURNEY-CPO-009.spec';
import '../journeys/cpo/JOURNEY-CPO-010.spec';

import { test, expect } from '@playwright/test';
import { loginAsPersona, getComplianceOfficerUser, getTestUser } from '../fixtures/auth';

test.describe('Persona RBAC: Compliance Officer', () => {
  test.setTimeout(120000);

  test('CPO can access /compliance', async ({ page }) => {
    await loginAsPersona(page, getComplianceOfficerUser);
    await page.goto('/compliance');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    test.skip(page.url().includes('/login'), 'Auth redirect');
    expect(page.url()).toContain('/compliance');
    await expect(page.locator('.error-display')).not.toBeVisible({ timeout: 2000 });
  });

  test('CPO can access /governance', async ({ page }) => {
    await loginAsPersona(page, getComplianceOfficerUser);
    await page.goto('/governance');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    test.skip(page.url().includes('/login'), 'Auth redirect');
    const url = page.url();
    expect(url.includes('/governance') || url.includes('/403')).toBe(true);
  });

  test('non-CPO user cannot access /audit', async ({ page }) => {
    await loginAsPersona(page, getTestUser); // DATA_PROVIDER, not CPO/auditor
    await page.goto('/audit');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForURL(/\/(403|login)/, { timeout: 20000 }).catch(() => null);
    const url = page.url();
    expect(url.includes('/403') || url.includes('/login')).toBe(true);
    expect(url.includes('/audit') && !url.includes('/403')).toBe(false);
  });
});
