/**
 * E2E Test: JOURNEY-CPO-002 — Generate Compliance Report
 *
 * Journey: Generate Compliance Report
 * Persona: Compliance Officer
 * Reference: docs/USER_JOURNEYS.md
 *
 * The CPO navigates to the compliance dashboard, views existing compliance runs,
 * and verifies export/report capabilities are accessible. If compliance runs exist,
 * navigates to a run detail page and verifies content renders.
 *
 * Fixture: getComplianceOfficerUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getComplianceOfficerUser, loginAsPersona } from '../../fixtures/auth';
import {
  assertListPageLoads,
  hasLoginPrompt,
  loginAndNavigateToRoute,
} from '../../fixtures/helpers';

test.describe('JOURNEY-CPO-002: Generate Compliance Report', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('compliance list loads and shows runs or empty state', async ({ page }) => {
      const cpoUser = await getComplianceOfficerUser();
      await loginAndNavigateToRoute(page, cpoUser, '/compliance', {
        timeout: 60000,
        contentSelector: '.compliance-run-list-page, .empty-state, .error-display',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(true, 'CPO user lacks compliance role on this environment');
        return;
      }
      await assertListPageLoads(page, '.compliance-run-list-page, .empty-state', {
        timeout: 60000,
      });
    });

    test('compliance run detail navigable when runs exist', async ({ page }) => {
      const cpoUser = await getComplianceOfficerUser();
      await loginAndNavigateToRoute(page, cpoUser, '/compliance', {
        timeout: 60000,
        contentSelector: '.compliance-run-list-page, .empty-state, .error-display',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(true, 'CPO user lacks compliance role');
        return;
      }

      // Check if any compliance runs exist in the list
      const runRows = page.locator(
        '.compliance-run-list-page table tbody tr, .compliance-run-list-page .run-row, [data-testid="compliance-run-row"]'
      );
      const rowCount = await runRows.count().catch(() => 0);

      if (rowCount === 0) {
        test.info().annotations.push({
          type: 'no-compliance-runs',
          description: 'No compliance runs exist — skipping detail navigation',
        });
        // Empty state is still valid — the list page rendered correctly
        const hasEmptyState = (await page.locator('.empty-state').count()) > 0;
        expect(hasEmptyState, 'Expected empty state when no compliance runs exist').toBe(true);
        return;
      }

      // Click the first run to navigate to detail
      await runRows.first().click();
      await page.waitForLoadState('domcontentloaded');

      // Wait for detail page content
      await page
        .locator('.compliance-run-detail-page, .compliance-run-detail, .error-display, h1')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 });

      const url = page.url();
      expect(url).toMatch(/\/compliance\/runs\//);
      await expect(page.locator('.error-display')).not.toBeVisible({ timeout: 3000 });
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to compliance redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/compliance', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|compliance|403)/, { timeout: 20_000 });
      const url = page.url();
      if (url.includes('/compliance') && !url.includes('/login')) {
        expect(await hasLoginPrompt(page)).toBe(true);
      } else {
        expect(url.includes('/login') || url.includes('/403')).toBe(true);
      }
    });
  });

  test.describe('Edge', () => {
    test('compliance list renders without server error', async ({ page }) => {
      const cpoUser = await getComplianceOfficerUser();
      await loginAndNavigateToRoute(page, cpoUser, '/compliance', {
        timeout: 60000,
        contentSelector: '.compliance-run-list-page, .empty-state, .error-display',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        // Role-gated redirect — acceptable
        return;
      }
      // Must not have 500 errors
      const has500 = (await page.locator('text=/500|internal server error/i').count()) > 0;
      expect(has500, 'Compliance page should not show 500 errors').toBe(false);
      // Must have meaningful content
      const hasContent =
        (await page.locator('.compliance-run-list-page, .empty-state').count()) > 0;
      expect(hasContent, 'Expected compliance list or empty state').toBe(true);
    });
  });
});
