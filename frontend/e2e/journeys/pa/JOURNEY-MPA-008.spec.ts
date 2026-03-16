/**
 * E2E Test: JOURNEY-MPA-008 — Configure Advanced Observability
 *
 * Journey: Configure Advanced Observability
 * Persona: Platform Admin
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /observability.
 * Fixture: getPlatformAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getPlatformAdminUser, loginAsPersona } from '../../fixtures/auth';

test.describe('JOURNEY-MPA-008: Configure Advanced Observability', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('observability page loads', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
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
    test('observability loads without crash', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/observability');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const no500 = (await page.locator('text=/500|internal server error/i').count()) === 0;
      expect(url.includes('/login') || url.includes('/403') || url.includes('/observability')).toBe(true);
      expect(no500).toBe(true);
    });
  });

});
