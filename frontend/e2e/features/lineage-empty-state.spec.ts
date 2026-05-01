/**
 * Phase 228 (REQ-LIN-005, 228.0.17) — empty-state branch.
 *
 * Separate from the strict-content spec at ``lineage.spec.ts`` so that
 * the strict assertion (3 nodes, 2 edges) and the empty-state branch
 * (no relationships → empty-state component) cannot mask each other:
 * a regression that returns 0 nodes for a seeded DAG must fail the
 * content spec; a regression that returns the empty-state for an
 * unrelated contract must fail this spec. Pre-Phase-228 both branches
 * lived as ``OR`` in a single assertion which silently masked either
 * direction.
 */
import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

const API_BASE = process.env.PLAYWRIGHT_API_BASE || '/api/v1';

/** Seed a single contract with NO lineage entries so the lineage tab
 *  must render the empty-state component. */
async function seedContractWithoutLineage(page, accessToken: string): Promise<string> {
  const runStamp = Date.now().toString(36);
  const id = `e2e-empty-lin-${runStamp}`;
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
    'info:',
    '  description: contract with no lineage relationships',
  ].join('\n');
  const res = await page.request.post(`${API_BASE}/contracts/`, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    data: {
      original_raw: body,
      original_spec_type: 'ODCS',
      original_format: 'YAML',
    },
  });
  if (!res.ok()) {
    const text = await res.text().catch(() => '');
    throw new Error(
      `Empty-state setup: POST ${API_BASE}/contracts/ failed ${res.status()}. ` +
        `Body: ${text.slice(0, 300)}.`,
    );
  }
  const data = (await res.json()) as { id?: string };
  if (!data.id) throw new Error('Empty-state setup: no id in 2xx response.');
  return data.id;
}

test.describe('Feature: Lineage — empty-state branch', () => {
  test.setTimeout(120000);

  test('contract without lineage entries renders empty-state component', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);

    const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
    if (!accessToken) throw new Error('No access_token after loginUser.');

    const contractId = await seedContractWithoutLineage(page, accessToken);

    await loginAndNavigateToRoute(page, user, `/contracts/${contractId}`, {
      timeout: 60000,
      contentSelector:
        '[data-testid="contract-detail-page"], .contract-detail-page',
    });
    await page.waitForURL(/\/contracts\/[0-9a-f-]+/i, { timeout: 15000 });
    await page.waitForSelector(
      '[data-testid="contract-detail-page"], .contract-detail-page',
      { timeout: 30000 },
    );

    const lineageTab = page
      .locator('button:has-text("Lineage"), [role="tab"]:has-text("Lineage"), a:has-text("Lineage")')
      .first();
    await lineageTab.waitFor({ state: 'visible', timeout: 10000 });
    await lineageTab.click();

    // REQ-LIN-005: empty-state component is rendered for a contract
    // with no lineage entries. The strict-content spec asserts the
    // graph branch; this spec asserts the empty branch. Each spec
    // owns ONE branch so a regression in either fails fast.
    await page
      .locator('.empty-state, [data-testid="empty-state"]')
      .first()
      .waitFor({ state: 'visible', timeout: 30000 });

    const emptyCount = await page
      .locator('.empty-state, [data-testid="empty-state"]')
      .count();
    expect(emptyCount).toBeGreaterThan(0);

    // The graph must NOT render — that branch belongs to the
    // strict-content spec.
    const graphCount = await page
      .locator('.react-flow__renderer, .react-flow')
      .count();
    expect(graphCount).toBe(0);
  });
});
