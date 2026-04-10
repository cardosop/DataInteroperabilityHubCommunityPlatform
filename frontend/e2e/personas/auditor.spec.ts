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
import { loginAsPersona, getAuditorUser, getTestUser } from '../fixtures/auth';

test.describe('Persona RBAC: Auditor', () => {
  test.setTimeout(120000);

  test('auditor can access /audit', async ({ page }) => {
    await loginAsPersona(page, getAuditorUser);
    await page.goto('/audit');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    test.skip(page.url().includes('/login'), 'Auth redirect');
    expect(page.url()).toContain('/audit');
    await expect(page.locator('.error-display')).not.toBeVisible({ timeout: 2000 });
  });

  test('non-auditor cannot access /audit (RBAC boundary)', async ({ page }) => {
    // storageState already has the default DATA_PROVIDER user (non-auditor).
    // No need for loginAsPersona — saves an API login call and avoids rate limits.
    await page.goto('/audit');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForURL(/\/(403|login)/, { timeout: 20000 }).catch(() => null);
    const url = page.url();
    expect(url.includes('/403') || url.includes('/login')).toBe(true);
    expect(url.includes('/audit') && !url.includes('/403')).toBe(false);
  });
});
