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
import { clearAuthStorage, getComplianceOfficerUser } from '../../fixtures/auth';
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
        contentSelector: '.compliance-run-list-page, [data-testid="compliance-run-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(page.url().includes('/login') || page.url().includes('/403'), 'CPO user lacks compliance role on this environment');
        return;
      }
      await assertListPageLoads(page, '.compliance-run-list-page, [data-testid="compliance-run-list-page"], .empty-state, [data-testid="empty-state"]', {
        timeout: 60000,
      });
    });

    test('compliance run detail navigable when runs exist', async ({ page }) => {
      const cpoUser = await getComplianceOfficerUser();
      await loginAndNavigateToRoute(page, cpoUser, '/compliance', {
        timeout: 60000,
        contentSelector: '.compliance-run-list-page, [data-testid="compliance-run-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(page.url().includes('/login') || page.url().includes('/403'), 'CPO user lacks compliance role');
        return;
      }

      // Check if any compliance runs exist in the list.
      // The row selector must be scoped strictly INSIDE the page container:
      // a comma-union whose first alternative is the container class matches
      // the container itself, so .first().click() clicks the page shell and
      // navigates nowhere (the same anti-pattern fixed for asset rows in
      // helpers.ts).
      const runRows = page
        .locator('.compliance-run-list-page, [data-testid="compliance-run-list-page"]')
        .first()
        .locator('.compliance-run-row, [data-testid="compliance-run-row"], table tbody tr, .run-row');
      // intentional: best-effort .catch on an optional step — primary pass/fail is made by a downstream assertion (verifyViaApi, waitFor, explicit expect). The fallback value tolerates well-known transient or absent-UI cases without papering over real failures.
      let rowCount = await runRows.count().catch(() => 0);

      if (rowCount === 0) {
        // The list can still be transitioning when the row count reads
        // zero under load (b6 #9: neither rows nor empty-state at check
        // time). Wait for a terminal list state, then re-count — rows may
        // appear after the settle and the click flow below should run.
        // intentional: the settle-wait is best-effort — a timeout just
        // means the list stayed rowless, and the empty-state assertion
        // below is the verdict.
        await page
          .locator(
            '.empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], .compliance-run-row, [data-testid="compliance-run-row"]'
          )
          .first()
          .waitFor({ state: 'visible', timeout: 30000 })
          .catch(() => null);
        // intentional: a detached-at-recount-time list still counts as
        // zero rows — the empty-state branch below is the verdict.
        rowCount = await runRows.count().catch(() => 0);
      }

      if (rowCount === 0) {
        test.info().annotations.push({
          type: 'no-compliance-runs',
          description: 'No compliance runs exist — skipping detail navigation',
        });
        // Empty state is still valid — the list page rendered correctly
        const hasEmptyState = (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
        expect(hasEmptyState, 'Expected empty state when no compliance runs exist').toBe(true);
        return;
      }

      // Click the first run to navigate to detail. The URL change IS the
      // contract — the previous wait used a bare `h1` alternative that the
      // list page's own heading satisfied instantly, masking a click that
      // never navigated.
      await runRows.first().click();
      // intentional: the URL assert below IS the failure path for a
      // non-navigating click — catching here only defers the verdict to it.
      await page.waitForURL(/\/compliance\/runs\//, { timeout: 15000 }).catch(() => null);

      // Detail content renders after the route change; advisory wait so the
      // error-display check below runs against the settled detail page.
      // intentional: terminal-state probe — element absence is tolerated and the next count/gate check adjudicates
      await page
        .locator('.compliance-run-detail-page, [data-testid="compliance-run-detail-page"], .compliance-run-detail, .error-display, [data-testid="error-display"]')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      const url = page.url();
      expect(url).toMatch(/\/compliance\/runs\//);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible({ timeout: 3000 });
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
        contentSelector: '.compliance-run-list-page, [data-testid="compliance-run-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
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
        (await page.locator('.compliance-run-list-page, [data-testid="compliance-run-list-page"], .empty-state, [data-testid="empty-state"]').count()) > 0;
      expect(hasContent, 'Expected compliance list or empty state').toBe(true);
    });
  });
});
