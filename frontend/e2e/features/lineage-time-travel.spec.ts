/**
 * Phase 228 F5 (228.F5.17) — UC-LIN-TIME-TRAVEL-001 E2E.
 *
 * Drives the full Phase 228 F5 surface in a real browser:
 *
 *   1. Visit the lineage tab.
 *   2. The time-travel controls render above the graph.
 *   3. Choosing a date in the past + clicking Apply re-fetches the
 *      visualization with `?as_of=<ISO8601>`.
 *   4. The graph repaints with whatever the historical state returns.
 *   5. Reset clears the anchor and re-fetches the live current view.
 *   6. axe-core a11y scan on the time-travel controls passes (no
 *      WCAG-A / AA violations).
 *
 * The spec is intentionally strict on `data-testid` selectors so a
 * future refactor that renames the controls fails this test by
 * name (228.F5.16 a11y data-testid contract).
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

const API_BASE = process.env.PLAYWRIGHT_API_BASE || '/api/v1';

async function seedContractForTimeTravel(page, accessToken: string): Promise<string> {
  const runStamp = Date.now().toString(36);
  const id = `e2e-tt-${runStamp}`;
  const body = [
    'kind: DataContract',
    'apiVersion: v3.0.2',
    `id: ${id}`,
    `name: ${id}`,
    'version: 1.0.0',
    'status: active',
    'schema:',
    `  - name: ${id}`,
    '    fields:',
    '      - name: id',
    '        type: string',
  ].join('\n');
  // The legacy POST /contracts/normalize/ no longer exists (b7 re-run
  // #12: the seed 404'd) — dry-run normalization now lives on
  // /contracts/validate-draft/ (no persistence). Seed through the
  // standard create path instead: the create serializer parses
  // original_raw and returns the persisted contract id.
  const resp = await page.request.post(`${API_BASE}/contracts/`, {
    data: {
      name: id,
      original_spec_type: 'ODCS',
      version: '1.0.0',
      original_raw: body,
      original_format: 'YAML',
    },
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  expect(
    resp.ok(),
    `seedContractForTimeTravel create failed ${resp.status()}: ` +
      `${(await resp.body()).toString('utf8').slice(0, 300)}`,
  ).toBeTruthy();
  const json = await resp.json();
  return json.id ?? json.contract_id ?? json.contract?.id;
}

test.describe('UC-LIN-TIME-TRAVEL-001 — point-in-time lineage', () => {
  test('time-travel controls drive ?as_of= and reset returns to live', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    // Phase 11.1 — loginUser returns void; the access_token lives in
    // apiClient module memory. Read it through the sanctioned probe the
    // verifyViaApi fixtures use so the seed POST below runs with the same
    // session the page uses.
    const accessToken = await page.evaluate(() => {
      const g = (window as unknown as { __getAccessToken?: () => string | null })
        .__getAccessToken;
      return (typeof g === 'function' ? g() : null) ?? localStorage.getItem('access_token');
    });
    if (!accessToken) {
      throw new Error(
        'lineage-time-travel: access token unavailable after loginUser — session not established'
      );
    }
    const contractId = await seedContractForTimeTravel(page, accessToken);

    await loginAndNavigateToRoute(page, user, `/contracts/${contractId}?tab=lineage`);

    // ContractDetailPage does NOT consume the ?tab= query param — the
    // page always opens on the Details tab, so the lineage visualization
    // (and its time-travel controls) only mount after an explicit tab
    // click (b7 re-run: the controls testid never appeared and both
    // tests timed out waiting for a component that couldn't mount).
    const lineageTab = page.getByRole('tab', { name: /Lineage/i });
    await lineageTab.waitFor({ state: 'visible', timeout: 10000 });
    await lineageTab.click();

    // Controls render.
    const controls = page.getByTestId('lineage-time-travel-controls');
    await expect(controls).toBeVisible();

    // Pick "yesterday at 12:00" — the date input is local-time.
    const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const pad = (n: number) => String(n).padStart(2, '0');
    const local =
      `${yesterday.getFullYear()}-${pad(yesterday.getMonth() + 1)}-${pad(yesterday.getDate())}` +
      `T12:00`;
    await page.getByTestId('lineage-asof-input').fill(local);

    // Capture the request the Apply button triggers — assert the
    // server gets the as_of param, not just the local UI state.
    const reqWaiter = page.waitForRequest(
      (req) =>
        req.url().includes(`/contracts/${contractId}/lineage/visualization/`) &&
        req.url().includes('as_of='),
    );
    await page.getByTestId('lineage-timetravel-apply').click();
    const req = await reqWaiter;
    expect(req.url()).toContain('as_of=');

    // Reset clears the anchor and returns to the live view. Do NOT wait
    // for a fresh no-as_of network request: when the initial live fetch
    // is still in flight, React Query coalesces the reset into that same
    // in-flight fetch (identical query key) and no second request fires —
    // which is correct behaviour, the mount fetch IS the live query. The
    // assertion must target the UI contract instead (b7 lineage-time-travel:
    // the reset waitForRequest flaked ~70% on this latency race).
    await page.getByTestId('lineage-timetravel-reset').click();
    // Anchor cleared — the diff-mode toggle row unmounts.
    await expect(page.getByTestId('lineage-diff-mode-toggle')).toHaveCount(0);
    // Live view returns — the historical (0-node) structureless empty state
    // is replaced by the live self-structure graph summary.
    await expect(
      page.getByTestId('contract-lineage-empty-structureless'),
    ).toHaveCount(0, { timeout: 15000 });
    // Non-zero node count: the live self-structure graph (the historical
    // anchor view of a freshly seeded contract has 0 nodes).
    await expect(page.getByText(/[1-9]\d* nodes · \d+ links/)).toBeVisible({
      timeout: 15000,
    });
  });

  test('a11y: time-travel controls + diff view have no WCAG A / AA violations', async ({ page }) => {
    const user = await getTestUser();
    // Phase 11.1 — loginUser returns void; the access_token lives in
    // localStorage / __getAccessToken (same contract as the sibling test).
    await loginUser(page, user);
    const accessToken = await page.evaluate(() => {
      const g = (window as unknown as { __getAccessToken?: () => string | null })
        .__getAccessToken;
      return typeof g === 'function' ? g() : localStorage.getItem('access_token');
    });
    if (!accessToken) {
      throw new Error(
        'lineage-time-travel: access token unavailable after loginUser — session not established'
      );
    }
    const contractId = await seedContractForTimeTravel(page, accessToken);
    await loginAndNavigateToRoute(page, user, `/contracts/${contractId}?tab=lineage`);

    // Same tab-activation requirement as the sibling test — the page
    // ignores ?tab= and opens on Details; click Lineage explicitly.
    const lineageTab = page.getByRole('tab', { name: /Lineage/i });
    await lineageTab.waitFor({ state: 'visible', timeout: 10000 });
    await lineageTab.click();

    await page.getByTestId('lineage-time-travel-controls').waitFor();

    // (1) Scan the time-travel controls.
    const controlsResults = await new AxeBuilder({ page })
      .include('[data-testid="lineage-time-travel-controls"]')
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();
    expect(controlsResults.violations).toEqual([]);

    // (2) Drive into diff mode + scan the diff view as well — DoD.4
    // requires the DIFF surface itself be a11y-clean, not just the
    // controls. Pick a date to seed an anchor, click the diff toggle.
    const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const pad = (n: number) => String(n).padStart(2, '0');
    await page.getByTestId('lineage-asof-input').fill(
      `${yesterday.getFullYear()}-${pad(yesterday.getMonth() + 1)}-${pad(yesterday.getDate())}T12:00`,
    );
    await page.getByTestId('lineage-timetravel-apply').click();
    await page.getByTestId('lineage-diff-mode-toggle').check();
    await page.getByTestId('lineage-diff-view').waitFor();

    const diffResults = await new AxeBuilder({ page })
      .include('[data-testid="lineage-diff-view"]')
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();
    expect(diffResults.violations).toEqual([]);
  });
});
