/**
 * Phase 228.F2.29 — Field-level lineage E2E.
 *
 * Field-level lineage assertions complement the existing
 * `lineage.spec.ts` (Phase 219.7 contract-tab lineage flow).  We
 * deliberately ship a separate spec rather than extend the legacy
 * file so:
 *
 * 1. The 228.0 in-flight refactor of `lineage.spec.ts` (uncommitted
 *    in the user's working tree) doesn't conflict with F2 work.
 * 2. The F2 surface gets its own dedicated E2E that can be
 *    enabled/disabled via the cross-browser matrix
 *    (`playwright.config.ts:projects.firefox/webkit` filters
 *    `**\/use-cases/contracts/UC-LIN-FIELD-EDIT-*.spec.ts` — but
 *    this `features/` spec is the broader integration check, not
 *    the use-case walkthrough at F2.28).
 *
 * What this spec asserts:
 *
 * - The contract Lineage tab renders the F2 entry-point (button)
 *   when the `contracts.lineage_field_editor` capability is on.
 * - The `?include_fields=true` query param on the visualization
 *   endpoint returns `field_nodes` + `field_links` keys (the F2.3
 *   wire shape).
 * - The Edit-lineage button navigates to `/contracts/:id/lineage/edit`.
 *
 * Real backend; skips when capability is OFF.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../fixtures/helpers';

test.describe('Field-level lineage (Phase 228.F2)', () => {
  // 240s: tail-of-batch churn stacks login backoff (~45s) + the 90s
  // navigation wait past the old 120s budget — the run died inside
  // waitForAppMainReady's settle wait with the budget expired (same
  // convention as DE-010/015 and features/integrations.spec.ts).
  test.setTimeout(240_000);

  test('include_fields=true visualisation returns field_nodes + field_links keys', async ({ page }) => {
    const user = await getTestUser();

    // Navigate to the contracts list as a logged-in user.  We use
    // the list as the auth + tenant-context scaffold; the actual
    // assertion uses page.request to call the API directly so the
    // spec doesn't depend on a specific contract's lineage shape.
    await loginAndNavigateToRoute(
      page, user, '/contracts',
      {
        timeout: 90_000,
        // `.contract-list` never existed — ContractListPage renders
        // `.contract-list-page` / `.contract-list-table` (b7: the poll
        // leaned on `main` alone and ate the full budget during the
        // auth-init stall).
        contentSelector:
          '.contract-list-page, [data-testid="contract-list-page"], .contract-list-table, [data-testid="contract-list-table"], main',
      },
    );
    if (page.url().includes('/login')) {
      test.skip(page.url().includes('/login'), 'Redirected to login — auth not available');
    }
    await waitForLoadingComplete(page, { timeout: 15_000 });

    // Pick the first available contract. The list rows are <tr> with
    // navigate() onClick (no anchors) — the row's checkbox testid
    // `contract-select-<uuid>` carries the contract id (b7: the
    // a[href^="/contracts/"] probe found zero anchors and skipped).
    const firstContract = page
      .locator('tbody [data-testid^="contract-select-"]:not([data-testid="contract-select-all"])')
      .first();
    if ((await firstContract.count()) === 0) {
      test.skip((await firstContract.count()) === 0, 'No contracts available in this environment');
    }
    const testId = (await firstContract.getAttribute('data-testid')) ?? '';
    const match = /^contract-select-(.+)$/.exec(testId);
    if (!match) {
      test.skip(!match, "Couldn't parse contract id from row");
    }
    const contractId = match[1];

    // Hit the visualization endpoint with include_fields=true.  The
    // spec at F2.3 promises field_nodes + field_links keys are
    // present on the JSON response when the param is set.
    // page.request does NOT share the page session — attach the bearer
    // token explicitly (b7: the unauthenticated call surfaced as a 500).
    const accessToken = await page.evaluate(() => {
      const g = (window as unknown as { __getAccessToken?: () => string | null })
        .__getAccessToken;
      return (typeof g === 'function' ? g() : null) ?? localStorage.getItem('access_token');
    });
    const apiBase =
      process.env.E2E_API_BASE_URL ?? '/api/v1';
    const response = await page.request.get(
      `${apiBase}/contracts/${contractId}/lineage/visualization/?format=json&max_depth=2&include_fields=true`,
      { headers: { Authorization: `Bearer ${accessToken}` } },
    );
    expect(response.status(), 'visualization endpoint responds 200').toBe(200);
    const body = await response.json();
    // The F2.3 wire-shape contract — these keys are always present
    // when include_fields=true (may be empty arrays for contracts
    // with no field-level edges).
    expect(body, 'field_nodes key present').toHaveProperty('field_nodes');
    expect(body, 'field_links key present').toHaveProperty('field_links');
    expect(Array.isArray(body.field_nodes), 'field_nodes is an array').toBe(true);
    expect(Array.isArray(body.field_links), 'field_links is an array').toBe(true);
  });

  test('Edit-lineage entrypoint navigates to /contracts/:id/lineage/edit when capability is on', async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(
      page, user, '/contracts',
      {
        timeout: 90_000,
        // `.contract-list` never existed — ContractListPage renders
        // `.contract-list-page` / `.contract-list-table` (b7: the poll
        // leaned on `main` alone and ate the full budget during the
        // auth-init stall).
        contentSelector:
          '.contract-list-page, [data-testid="contract-list-page"], .contract-list-table, [data-testid="contract-list-table"], main',
      },
    );
    if (page.url().includes('/login')) {
      test.skip(page.url().includes('/login'), 'Redirected to login');
    }
    await waitForLoadingComplete(page, { timeout: 15_000 });

    // Same dead-selector class as the sibling test: rows are <tr>, not
    // anchors (b7: zero anchors → unconditional skip).
    const firstContract = page.locator('.contract-list-table tbody tr.contract-row').first();
    if ((await firstContract.count()) === 0) {
      test.skip((await firstContract.count()) === 0, 'No contracts available');
    }
    await firstContract.click();
    await waitForLoadingComplete(page, { timeout: 15_000 });

    // Switch to Lineage tab.
    const lineageTab = page.getByRole('tab', { name: /lineage/i }).first();
    if ((await lineageTab.count()) === 0) {
      test.skip((await lineageTab.count()) === 0, 'No Lineage tab on this contract');
    }
    await lineageTab.click();
    await waitForLoadingComplete(page, { timeout: 15_000 });

    // Capability gate.
    const entrypoint = page.getByTestId('lineage-edit-entrypoint');
    if ((await entrypoint.count()) === 0) {
      test.skip((await entrypoint.count()) === 0, 'lineage_field_editor capability OFF in this environment');
    }
    await entrypoint.locator('button').click();

    // We're now on the editor page.
    await expect(page).toHaveURL(/\/contracts\/[^/]+\/lineage\/edit$/);
    await expect(page.getByTestId('lineage-edit-page')).toBeVisible({
      timeout: 15_000,
    });
  });
});
