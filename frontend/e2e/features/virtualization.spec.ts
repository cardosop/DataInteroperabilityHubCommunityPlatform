/**
 * E2E Feature: Virtualization
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /virtualization.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { assertListPageLoads } from '../fixtures/helpers';

test.describe('Feature: Virtualization', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('virtualization route loads', async ({ page }) => {
      await page.goto('/virtualization');
      await page.waitForLoadState('domcontentloaded');
      await assertListPageLoads(page, '.virtualization-page, .empty-state, h1', { timeout: 60000 });
    });
  });

  test.describe('Edge', () => {
    test('virtualization may show capability-gated content', async ({ page }) => {
      await page.goto('/virtualization');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url).toMatch(/\/(virtualization|login|403|unavailable)/);
    });
  });
});
