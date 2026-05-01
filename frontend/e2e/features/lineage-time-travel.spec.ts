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
  const resp = await page.request.post(`${API_BASE}/contracts/normalize/`, {
    data: { raw: body, original_format: 'YAML', original_spec_type: 'ODCS' },
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  expect(resp.ok()).toBeTruthy();
  const json = await resp.json();
  return json.id ?? json.contract_id ?? json.contract?.id;
}

test.describe('UC-LIN-TIME-TRAVEL-001 — point-in-time lineage', () => {
  test('time-travel controls drive ?as_of= and reset returns to live', async ({ page }) => {
    const user = await getTestUser();
    const { accessToken } = await loginUser(page, user);
    const contractId = await seedContractForTimeTravel(page, accessToken);

    await loginAndNavigateToRoute(page, `/contracts/${contractId}?tab=lineage`, user);

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

    // Reset clears the anchor and re-fetches without as_of.
    const resetReqWaiter = page.waitForRequest(
      (req) =>
        req.url().includes(`/contracts/${contractId}/lineage/visualization/`) &&
        !req.url().includes('as_of='),
    );
    await page.getByTestId('lineage-timetravel-reset').click();
    await resetReqWaiter;
  });

  test('a11y: time-travel controls + diff view have no WCAG A / AA violations', async ({ page }) => {
    const user = await getTestUser();
    const { accessToken } = await loginUser(page, user);
    const contractId = await seedContractForTimeTravel(page, accessToken);
    await loginAndNavigateToRoute(page, `/contracts/${contractId}?tab=lineage`, user);

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
