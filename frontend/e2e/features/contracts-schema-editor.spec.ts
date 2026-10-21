/**
 * Phase 227 Wave 1 (227.L5.13) — Schema editor E2E.
 *
 * Walks the Schema-tab editor flow against the running app. Per the
 * 2026-04-30 ungate directive the tab is always visible — no
 * ``VITE_FEATURE_SCHEMA_EDITOR_ENABLED`` gate to skip on.
 *
 * What this spec asserts (golden path)
 * ------------------------------------
 * 1. The Schema tab is reachable from the contract editor.
 * 2. The editor renders models + fields from an existing contract.
 * 3. axe-core a11y check on the editor surface produces no violations
 *    of the rules we treat as load-bearing (forms, buttons, labels).
 *
 * Deterministic seeding (b7): the spec previously skipped when the
 * tenant had no editable contract ("staging clean DB") or the first
 * row was a legacy contract without a Schema tab — both
 * environment-dependent skips that masked regressions. It now seeds
 * its own ODCS contract through the same API the UI uses (same
 * pattern as lineage-time-travel's seedContractForTimeTravel) and
 * navigates straight to its editor, so the Schema tab + ModelsEditor
 * assertions run against a known contract every time.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { getTestUser, loginUser } from '../fixtures/auth';

const API_BASE = process.env.PLAYWRIGHT_API_BASE || '/api/v1';

/** Seed a fresh ODCS contract with one model + one field, return its id. */
async function seedEditableContract(page: Page): Promise<string> {
  const accessToken = await page.evaluate(() => {
    const g = (window as unknown as { __getAccessToken?: () => string | null })
      .__getAccessToken;
    return (typeof g === 'function' ? g() : null) ?? localStorage.getItem('access_token');
  });
  if (!accessToken) {
    throw new Error(
      'contracts-schema-editor: access token unavailable after loginUser — session not established',
    );
  }
  const runStamp = Date.now().toString(36);
  const id = `e2e-schema-${runStamp}`;
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
    `seedEditableContract create failed ${resp.status()}: ` +
      // intentional: diagnostic-only read — the body preview is best-effort extra context for the failure message; the hard failure is the expect above.
      `${(await resp.text().catch(() => '')).slice(0, 300)}`,
  ).toBeTruthy();
  const json = await resp.json();
  const contractId = json.id ?? json.contract_id ?? json.contract?.id;
  expect(contractId, 'seed create response must carry a contract id').toBeTruthy();
  return contractId as string;
}

test.describe('Feature: Contracts — Schema editor (Phase 227 L5)', () => {
  test('Schema tab is reachable from the contract editor', async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);

    // Seed before any page.goto: the in-memory token dies on a full
    // reload (Phase 11.1), so the seed runs on the page loginUser
    // leaves (same contract as the lineage specs).
    const contractId = await seedEditableContract(page);

    await page.goto(`/contracts/${contractId}/edit`, { waitUntil: 'domcontentloaded' });

    // The Schema tab should be visible (no flag-gate).
    const schemaTab = page.getByTestId('editor-tab-schema');
    await expect(schemaTab).toBeVisible({ timeout: 15000 });
    await schemaTab.click();
    // The ModelsEditor surface should mount.
    await expect(page.getByTestId('models-editor')).toBeVisible({ timeout: 10000 });
  });

  test('a11y check on the Schema editor', async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);

    const contractId = await seedEditableContract(page);

    await page.goto(`/contracts/${contractId}/edit`, { waitUntil: 'domcontentloaded' });

    const schemaTab = page.getByTestId('editor-tab-schema');
    await expect(schemaTab).toBeVisible({ timeout: 15000 });
    await schemaTab.click();
    await page.getByTestId('models-editor').waitFor({ timeout: 10000 });

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .include('[data-testid="models-editor"]')
      .analyze();
    expect(results.violations).toEqual([]);
  });
});
