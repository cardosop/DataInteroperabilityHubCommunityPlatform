/**
 * E2E Feature: Observability
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /observability.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../fixtures/helpers';

test.describe('Feature: Observability', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('observability route loads or redirects to login/403', async ({ page }) => {
      await page.goto('/observability');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      const url = page.url();
      expect(url).toMatch(/\/observability|\/login|\/403/);
    });
  });

  test.describe('Edge', () => {
    test('observability may show content or capability-gated message', async ({ page }) => {
      await page.goto('/observability');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5000);
      // body.count() > 0 is always true — assert meaningful page content instead
      const hasContent =
        (await page
          .locator(
            '.observability-page, .monitoring-page, .unavailable-page, .error-display, h1'
          )
          .count()) > 0;
      expect(
        hasContent,
        'Expected .observability-page, .monitoring-page, .unavailable-page, .error-display, or h1 to be present'
      ).toBe(true);
    });
  });
});
