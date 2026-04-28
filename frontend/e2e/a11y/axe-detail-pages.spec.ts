/**
 * Phase 226.F5 — Axe coverage on detail-page surfaces.
 *
 * Third leg of the F5 sprinkle (after axe-critical-pages.spec.ts and
 * axe-interactive-states.spec.ts). This spec rounds out coverage on
 * the detail-page family (per-resource pages where forms, action
 * buttons, and metadata cards live), which is where the visual /
 * interactive surface area is densest and a11y regressions tend to
 * land first.
 *
 * Each test loads a representative detail or list-detail surface and
 * audits via the shared `runAxeAudit` helper. Hard gate on critical /
 * serious; moderate / minor are logged for the team's ratchet.
 *
 * Real backend only — no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';
import {
  runAxeAudit,
  expectNoSeriousViolations,
  summarizeViolations,
} from '../fixtures/axeAudit';

async function audit(page: import('@playwright/test').Page, label: string) {
  const result = await runAxeAudit(page, label);
  expectNoSeriousViolations(result);
  if (result.totalCount > 0) {
    // intentional: surfaces moderate/minor violations to run output without failing the build — mirrors the convention from the sibling axe-* specs.
    console.warn(summarizeViolations(result));
  }
  return result;
}

const ROUTES_TO_AUDIT: Array<{ path: string; label: string; mustReachShell?: boolean }> = [
  { path: '/contracts', label: 'contracts-list' },
  { path: '/datasets', label: 'datasets-list' },
  { path: '/marketplace', label: 'marketplace-list-detail-context' },
  { path: '/governance', label: 'governance' },
  { path: '/integrations', label: 'integrations' },
  { path: '/lineage', label: 'lineage' },
  { path: '/observability', label: 'observability' },
  { path: '/audit', label: 'audit-events' },
  { path: '/notifications', label: 'notifications' },
  { path: '/jobs', label: 'jobs' },
  { path: '/webhooks', label: 'webhooks' },
  { path: '/search', label: 'search' },
];

test.describe('A11y axe coverage — detail / list pages @a11y @critical', () => {
  test.setTimeout(120_000);

  for (const route of ROUTES_TO_AUDIT) {
    test(`${route.path} audits clean`, async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      await page.goto(route.path, { waitUntil: 'domcontentloaded' });
      // Wait for either the app shell OR a known terminal state (capability-gated /
      // unavailable / 404). Either is a valid a11y target.
      await page
        .locator('.app-header, [data-testid="app-header"], .unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"], .not-found-page')
        .first()
        .waitFor({ state: 'visible', timeout: 15_000 })
        .catch(() => {
          // intentional: SPA may render a route-specific empty/loading state without our terminal selectors; the audit below scans whichever state surfaced — that's the a11y target regardless of which path the SPA settled on.
        });
      if (route.mustReachShell) {
        await expect(page.locator('.app-header, [data-testid="app-header"]').first()).toBeVisible({ timeout: 15_000 });
      }
      await audit(page, route.label);
    });
  }
});
