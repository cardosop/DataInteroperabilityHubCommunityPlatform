/**
 * Persona Aggregator: Auditor
 * Imports and runs all AUD journey specs (JOURNEY-AUD-001 through AUD-006).
 * Run: npm run test:e2e -- e2e/personas/auditor.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

import '../journeys/aud/JOURNEY-AUD-001.spec';
import '../journeys/aud/JOURNEY-AUD-002.spec';
import '../journeys/aud/JOURNEY-AUD-003.spec';
import '../journeys/aud/JOURNEY-AUD-004.spec';
import '../journeys/aud/JOURNEY-AUD-005.spec';
import '../journeys/aud/JOURNEY-AUD-006.spec';

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
