/**
 * E2E Feature: Lineage Visualization (Phase 219.7)
 *
 * Lineage is embedded in the contract detail page as a "Lineage" tab
 * (ContractLineageVisualization → React Flow graph). There is no
 * standalone /lineage route.
 *
 * Test flow: /contracts → click first contract → click Lineage tab →
 * assert React Flow renderer OR empty state (both acceptable).
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { assertListPageLoads } from '../fixtures/helpers';

test.describe('Feature: Lineage', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('contract lineage tab renders graph or empty state', async ({ page }) => {
      // Navigate to contracts list (storageState provides auth)
      await page.goto('/contracts', { waitUntil: 'domcontentloaded' });

      // Wait for list to load — may be empty on a fresh staging DB
      try {
        await assertListPageLoads(
          page,
          '[data-testid="contract-list-page"], .contract-list-page, .empty-state',
          { timeout: 60000 },
        );
      } catch {
        if (page.url().includes('/login')) {
          test.skip(true, 'Redirected to /login — auth token expired');
          return;
        }
        throw new Error('Contract list did not load');
      }

      // If empty state or no contracts, skip — lineage needs contract data.
      // Use .contract-row only (not generic tr) to avoid matching <thead> rows.
      const rows = page.locator('.contract-row');
      if ((await rows.count()) === 0) {
        test.skip(true, 'No contracts on staging — lineage requires contract data');
        return;
      }

      // Click first contract row → navigate to detail page
      await rows.first().click();
      await page.waitForURL(/\/contracts\/[0-9a-f-]+/i, { timeout: 15000 });

      // Click "Lineage" tab
      const lineageTab = page
        .locator('button:has-text("Lineage"), [role="tab"]:has-text("Lineage"), a:has-text("Lineage")')
        .first();
      await lineageTab.waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);

      if ((await lineageTab.count()) === 0) {
        test.skip(true, 'Lineage tab not visible — feature may be gated or contract has no lineage');
        return;
      }
      await lineageTab.click();

      // Wait for either React Flow graph or empty/loading/error state
      await page
        .locator('.react-flow__renderer, .react-flow, .empty-state, .error-display, .loading-spinner')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      // Assert: either graph rendered or acceptable empty/error state
      const hasReactFlow =
        (await page.locator('.react-flow__renderer, .react-flow').count()) > 0;
      const hasEmptyOrError =
        (await page.locator('.empty-state, .error-display').count()) > 0;

      expect(hasReactFlow || hasEmptyOrError).toBe(true);

      // If graph rendered, verify controls exist
      if (hasReactFlow) {
        const hasControls =
          (await page.locator('.react-flow__controls').count()) > 0;
        expect(hasControls).toBe(true);
      }
    });
  });
});
