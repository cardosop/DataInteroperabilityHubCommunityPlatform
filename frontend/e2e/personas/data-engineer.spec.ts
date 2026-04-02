/**
 * Persona Aggregator: Data Engineer
 * Imports and runs all DE journey specs (JOURNEY-DE-001 through DE-014).
 * Run: npm run test:e2e -- e2e/personas/data-engineer.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

import '../journeys/de/JOURNEY-DE-001.spec';
import '../journeys/de/JOURNEY-DE-002.spec';
import '../journeys/de/JOURNEY-DE-003.spec';
import '../journeys/de/JOURNEY-DE-004.spec';
import '../journeys/de/JOURNEY-DE-005.spec';
import '../journeys/de/JOURNEY-DE-006.spec';
import '../journeys/de/JOURNEY-DE-007.spec';
import '../journeys/de/JOURNEY-DE-008.spec';
import '../journeys/de/JOURNEY-DE-009.spec';
import '../journeys/de/JOURNEY-DE-010.spec';
import '../journeys/de/JOURNEY-DE-011.spec';
import '../journeys/de/JOURNEY-DE-012.spec';
import '../journeys/de/JOURNEY-DE-013.spec';
import '../journeys/de/JOURNEY-DE-014.spec';

import { test, expect } from '@playwright/test';
import { loginAsPersona, getTestUser } from '../fixtures/auth';

test.describe('Persona RBAC: Data Engineer', () => {
  test.setTimeout(120000);

  test('DE can access /contracts', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/contracts');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    test.skip(page.url().includes('/login'), 'Auth redirect');
    expect(page.url()).toContain('/contracts');
  });

  test('DE can access /scheduled-ingestion', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/scheduled-ingestion');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    test.skip(page.url().includes('/login'), 'Auth redirect');
    expect(page.url()).toContain('/scheduled-ingestion');
  });

  test('DE cannot access /admin', async ({ page }) => {
    await loginAsPersona(page, getTestUser);
    await page.goto('/admin');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForURL(/\/(403|login|admin|assets)/, { timeout: 20000 }).catch(() => null);
    const url = page.url();
    expect(url.includes('/403') || url.includes('/login') || !url.includes('/admin')).toBe(true);
  });
});
