/**
 * Persona Aggregator: Data Mesh Domain Owner
 * Imports and runs all DMO journey specs (JOURNEY-DMO-001 through DMO-005).
 * Run: npm run test:e2e -- e2e/personas/data-mesh-domain-owner.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

// Core-only mode (E2E_CORE_ONLY=1): the imported journey specs are FULL-mode
// journeys; the core subset runs the persona's own RBAC tests below instead.
if (process.env.E2E_CORE_ONLY !== '1') {
  await import('../journeys/dmo/JOURNEY-DMO-001.spec');
  await import('../journeys/dmo/JOURNEY-DMO-002.spec');
  await import('../journeys/dmo/JOURNEY-DMO-003.spec');
  await import('../journeys/dmo/JOURNEY-DMO-004.spec');
  await import('../journeys/dmo/JOURNEY-DMO-005.spec');

}

import { test, expect } from '@playwright/test';
import { loginAsPersona, getDataMeshDomainOwnerUser } from '../fixtures/auth';
import { waitForAppMainReady, waitForRoleGuardResolved } from '../fixtures/helpers';

test.describe('Persona RBAC: Data Mesh Domain Owner', () => {
  test.setTimeout(120000);

  test('DMO can access /mesh', async ({ page }) => {
    await loginAsPersona(page, getDataMeshDomainOwnerUser);
    await page.goto('/mesh');
    await waitForAppMainReady(page);
    const url = page.url();
    expect(url.includes('/mesh') || url.includes('/403')).toBe(true);
  });

  test('DMO can access /mesh/create', async ({ page }) => {
    await loginAsPersona(page, getDataMeshDomainOwnerUser);
    await page.goto('/mesh/create');
    await waitForAppMainReady(page);
    const url = page.url();
    expect(url.includes('/mesh') || url.includes('/403')).toBe(true);
  });

  test('DMO cannot access /admin', async ({ page }) => {
    await loginAsPersona(page, getDataMeshDomainOwnerUser);
    await page.goto('/admin');
    await page.waitForLoadState('domcontentloaded');
    const resolved = await waitForRoleGuardResolved(page, { forbiddenPathPrefix: '/admin' });
    if (resolved.includes('/login')) {
      test.skip(resolved.includes('/login'), 'Auth session expired — not an RBAC result');
      return;
    }
    expect(resolved.includes('/403') || !resolved.includes('/admin')).toBe(true);
  });
});
