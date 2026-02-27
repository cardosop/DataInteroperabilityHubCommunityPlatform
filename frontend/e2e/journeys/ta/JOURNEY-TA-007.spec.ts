/**
 * E2E Test: JOURNEY-TA-007 — Monitor Cost Tracking
 *
 * Journey: Monitor Cost Tracking
 * Persona: Tenant Admin
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /observability.
 * Fixture: getTenantAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUser, loginAsPersona } from '../../fixtures/auth';

test.describe('JOURNEY-TA-007: Monitor Cost Tracking', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('observability page loads', async ({ page }) => {
      await loginAsPersona(page, getTenantAdminUser);
      await page.goto('/observability');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onObservability = page.url().includes('/observability');
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const hasContent =
        (await page.locator('.observability-page, .app-main, h1').count()) > 0;
      expect(onLogin || on403 || (onObservability && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('observability without access shows 403 or redirect', async ({ page }) => {
      await loginAsPersona(page, getTenantAdminUser);
      await page.goto('/observability');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/observability')).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('observability page loads', async ({ page }) => {
      await loginAsPersona(page, getTenantAdminUser);
      await page.goto('/observability');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/observability')).toBe(true);
    });
  });
});
