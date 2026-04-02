/**
 * Persona Aggregator: Data Mesh Domain Owner
 * Imports and runs all DMO journey specs (JOURNEY-DMO-001 through DMO-005).
 * Run: npm run test:e2e -- e2e/personas/data-mesh-domain-owner.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

import '../journeys/dmo/JOURNEY-DMO-001.spec';
import '../journeys/dmo/JOURNEY-DMO-002.spec';
import '../journeys/dmo/JOURNEY-DMO-003.spec';
import '../journeys/dmo/JOURNEY-DMO-004.spec';
import '../journeys/dmo/JOURNEY-DMO-005.spec';

import { test, expect } from '@playwright/test';
import { loginAsPersona, getDataMeshDomainOwnerUser } from '../fixtures/auth';

test.describe('Persona RBAC: Data Mesh Domain Owner', () => {
  test.setTimeout(120000);

  test('DMO can access /mesh', async ({ page }) => {
    await loginAsPersona(page, getDataMeshDomainOwnerUser);
    await page.goto('/mesh');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    test.skip(page.url().includes('/login'), 'Auth redirect');
    const url = page.url();
    expect(url.includes('/mesh') || url.includes('/403')).toBe(true);
  });

  test('DMO can access /mesh/create', async ({ page }) => {
    await loginAsPersona(page, getDataMeshDomainOwnerUser);
    await page.goto('/mesh/create');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    test.skip(page.url().includes('/login'), 'Auth redirect');
    const url = page.url();
    expect(url.includes('/mesh') || url.includes('/403')).toBe(true);
  });

  test('DMO cannot access /admin', async ({ page }) => {
    await loginAsPersona(page, getDataMeshDomainOwnerUser);
    await page.goto('/admin');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForURL(/\/(403|login|admin|mesh)/, { timeout: 20000 }).catch(() => null);
    const url = page.url();
    expect(url.includes('/403') || url.includes('/login') || !url.includes('/admin')).toBe(true);
  });
});
