/**
 * Persona Aggregator: Auditor
 * Imports and runs all AUD journey specs (JOURNEY-AUD-001 through AUD-006).
 * Run: npm run test:e2e -- e2e/personas/auditor.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

// Core-only mode (E2E_CORE_ONLY=1): the imported journey specs are FULL-mode
// journeys; the core subset runs the persona's own RBAC tests below instead.
if (process.env.E2E_CORE_ONLY !== '1') {
  await import('../journeys/aud/JOURNEY-AUD-001.spec');
  await import('../journeys/aud/JOURNEY-AUD-002.spec');
  await import('../journeys/aud/JOURNEY-AUD-003.spec');
  await import('../journeys/aud/JOURNEY-AUD-004.spec');
  await import('../journeys/aud/JOURNEY-AUD-005.spec');
  await import('../journeys/aud/JOURNEY-AUD-006.spec');
}

import { test, expect } from '@playwright/test';
import { loginAsPersona, getAuditorUser } from '../fixtures/auth';
import { waitForAppMainReady, waitForRoleGuardResolved } from '../fixtures/helpers';

test.describe('Persona RBAC: Auditor', () => {
  test.setTimeout(120000);

  test('auditor can access /audit', async ({ page }) => {
    await loginAsPersona(page, getAuditorUser);
    await page.goto('/audit');
    await waitForAppMainReady(page);
    expect(page.url()).toContain('/audit');
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 2000 });
  });

  test('non-auditor cannot access /audit (RBAC boundary)', async ({ page }) => {
    await page.goto('/audit');
    await page.waitForLoadState('domcontentloaded');
    const resolved = await waitForRoleGuardResolved(page, { forbiddenPathPrefix: '/audit' });
    expect(resolved.includes('/403') || resolved.includes('/login')).toBe(true);
  });
});
