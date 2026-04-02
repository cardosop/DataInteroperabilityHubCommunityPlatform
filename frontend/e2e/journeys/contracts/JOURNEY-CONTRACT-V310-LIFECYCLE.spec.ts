/**
 * JOURNEY-CONTRACT-V310-LIFECYCLE
 *
 * Full lifecycle E2E test for ODCS v3.1.0 contracts:
 *   1. Create v3.1.0 contract via API (with relationships)
 *   2. Verify spec version badge on detail page
 *   3. Verify RelationshipsPanel renders with rows
 *   4. Click target contract link in relationships panel
 *   5. Open export modal, select lower version, verify warning
 *   6. Export as v3.0.2 YAML -> verify relationships stripped
 *   7. Export as v3.1.0 YAML -> verify relationships preserved + apiVersion
 */

import { test, expect } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { getTestUser, loginUser } from '../../fixtures/auth';

const __currentDir = path.dirname(fileURLToPath(import.meta.url));

// Run tests serially — they share state from beforeAll and we need to
// avoid rate-limiting from concurrent logins.
test.describe.configure({ mode: 'serial' });

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http')
    ? process.env.VITE_API_BASE_URL
    : `http://localhost:${DEFAULT_API_PORT}/api/v1`);

function readFixture(name: string): string {
  const fixtureDir = path.resolve(__currentDir, '..', '..', '..', '..', 'tests', 'fixtures', 'contracts');
  return fs.readFileSync(path.join(fixtureDir, name), 'utf-8');
}

/** Semantic version comparison: returns -1, 0, or 1. */
function semverCompare(a: string, b: string): number {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const na = pa[i] || 0;
    const nb = pb[i] || 0;
    if (na < nb) return -1;
    if (na > nb) return 1;
  }
  return 0;
}

/** Login via API with retry on 429/5xx. */
async function getAccessToken(): Promise<string> {
  const user = await getTestUser();
  for (let attempt = 0; attempt < 5; attempt++) {
    if (attempt > 0) await new Promise((r) => setTimeout(r, 3000 * attempt));
    try {
      const loginRes = await fetch(`${API_BASE}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: user.email, password: user.password }),
      });
      if (loginRes.status === 429 || loginRes.status >= 500) continue;
      if (!loginRes.ok) {
        throw new Error(`Login failed: ${loginRes.status} ${await loginRes.text()}`);
      }
      const data = await loginRes.json();
      return data.access_token || data.access || data.token;
    } catch (e: unknown) {
      if (attempt === 4) throw e;
      if (e instanceof Error && e.message?.includes('Login failed')) throw e;
    }
  }
  throw new Error('Login failed after 5 retries');
}

interface CreatedContract { id: string; original_spec_version: string }

async function createContractViaApi(
  token: string,
  raw: string,
  specType: string,
  format: string,
): Promise<CreatedContract> {
  const res = await fetch(`${API_BASE}/contracts/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      original_raw: raw,
      original_spec_type: specType,
      original_format: format,
    }),
  });
  if (!res.ok) {
    throw new Error(`Contract create failed: ${res.status} ${await res.text()}`);
  }
  const data = await res.json();
  return { id: data.id, original_spec_version: data.original_spec_version || 'unknown' };
}

/** Poll until normalization completes. Throws on failure with diagnostics. */
async function waitForNormalization(token: string, contractId: string): Promise<void> {
  for (let i = 0; i < 60; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    const res = await fetch(`${API_BASE}/contracts/${contractId}/`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) continue;
    const c = await res.json();
    const s = c.normalization_status;
    if (s === 'NORMALIZATION_FAILED') {
      throw new Error(
        `Normalization FAILED for ${contractId}: ${JSON.stringify(c.normalization_errors)}`,
      );
    }
    if (s === 'NORMALIZED_OK' || s === 'NORMALIZED_WITH_WARNINGS') {
      return;
    }
  }
  throw new Error(`Normalization did not complete for contract ${contractId} within 120s`);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe('JOURNEY-CONTRACT-V310-LIFECYCLE', () => {
  let token: string;
  let contractId: string;
  let contractSpecVersion: string;
  let contract302Id: string;

  test.beforeAll(async () => {
    token = await getAccessToken();

    // Create both contracts upfront to avoid rate limiting in individual tests
    const raw310 = readFixture('odcs_v3_1_0_with_relationships.yaml');
    const c310 = await createContractViaApi(token, raw310, 'ODCS', 'YAML');
    contractId = c310.id;
    contractSpecVersion = c310.original_spec_version;

    const raw302 = readFixture('odcs_v3_0_2_reference.yaml');
    const c302 = await createContractViaApi(token, raw302, 'ODCS', 'YAML');
    contract302Id = c302.id;

    // Wait for both to normalize (throws on failure)
    await Promise.all([
      waitForNormalization(token, contractId),
      waitForNormalization(token, contract302Id),
    ]);
  });

  test.describe('Success', () => {
    test('spec version badge shows ODCS v3.1.0', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);

      await page.goto(`/contracts/${contractId}`);
      await page.waitForSelector('.contract-detail-page', { timeout: 30000 });

      const badge = page.locator('.spec-version-badge');
      await expect(badge).toBeVisible({ timeout: 10000 });
      const text = await badge.textContent();
      expect(text).toContain('ODCS');
      expect(text).toContain(contractSpecVersion);
    });

    test('RelationshipsPanel renders with foreignKey row', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);

      await page.goto(`/contracts/${contractId}`);
      await page.waitForSelector('.contract-detail-page', { timeout: 30000 });

      // The v3.1.0 fixture has relationships — panel MUST show them
      const panel = page.locator('.relationships-panel');
      await expect(panel).toBeVisible({ timeout: 15000 });

      // Must have at least 1 relationship row (fixture has 1 foreignKey)
      const rows = page.locator('.rel-row');
      await expect(rows.first()).toBeVisible({ timeout: 10000 });
      const rowCount = await rows.count();
      expect(rowCount).toBeGreaterThanOrEqual(1);

      // Verify relationship type matches fixture
      const typeCell = page.locator('.rel-cell-type').first();
      await expect(typeCell).toContainText('foreignKey');
    });

    test('relationship target link has correct href', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);

      await page.goto(`/contracts/${contractId}`);
      await page.waitForSelector('.contract-detail-page', { timeout: 30000 });

      // Wait for relationship rows to render
      const rows = page.locator('.rel-row');
      await expect(rows.first()).toBeVisible({ timeout: 15000 });

      // The target link should exist and point to a contract
      const link = page.locator('.rel-link').first();
      await expect(link).toBeVisible({ timeout: 5000 });
      const href = await link.getAttribute('href');
      expect(href).toContain('/contracts/');
      // Fixture references "customers-contract" as target_contract
      expect(href).toContain('customers-contract');
    });

    test('export modal: downgrade to older version shows warning', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);

      await page.goto(`/contracts/${contractId}`);
      await page.waitForSelector('.contract-detail-page', { timeout: 30000 });

      // Open export modal
      await page.locator('button:has-text("Export")').click();
      await page.waitForSelector('.export-modal', { timeout: 5000 });

      // Find a version strictly lower than the contract's version using semver
      const versionSelect = page.locator('#export-version');
      const options = await versionSelect.locator('option').allTextContents();

      let downgradeTo: string | null = null;
      for (const opt of options) {
        const v = opt.split(' ')[0];
        if (v && /^\d+\.\d+\.\d+$/.test(v) && semverCompare(v, contractSpecVersion) < 0 && !opt.includes('requires manual')) {
          downgradeTo = v;
          break;
        }
      }

      expect(downgradeTo).not.toBeNull();
      await versionSelect.selectOption(downgradeTo!);

      // Warning banner should appear
      const warning = page.locator('.export-warning');
      await expect(warning).toBeVisible({ timeout: 3000 });
      const warningText = await warning.textContent();
      expect(warningText).toContain('drop');
    });

    test('export as v3.0.2: downloaded file has no relationships key', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);

      await page.goto(`/contracts/${contractId}`);
      await page.waitForSelector('.contract-detail-page', { timeout: 30000 });

      await page.locator('button:has-text("Export")').click();
      await page.waitForSelector('.export-modal', { timeout: 5000 });
      await page.selectOption('#export-version', '3.0.2');

      const downloadPromise = page.waitForEvent('download', { timeout: 30000 });
      await page.locator('.export-modal button.btn-primary').click();
      const download = await downloadPromise;

      const filePath = await download.path();
      expect(filePath).toBeTruthy();
      const content = fs.readFileSync(filePath!, 'utf-8');

      // Downgrade: relationships should be stripped
      expect(content).not.toMatch(/^relationships:/m);
      // Should reference 3.0.2
      expect(content).toMatch(/3\.0\.2/);
    });

    test('export as v3.1.0: relationships and apiVersion preserved', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);

      await page.goto(`/contracts/${contractId}`);
      await page.waitForSelector('.contract-detail-page', { timeout: 30000 });

      await page.locator('button:has-text("Export")').click();
      await page.waitForSelector('.export-modal', { timeout: 5000 });
      await page.selectOption('#export-version', '3.1.0');

      // No downgrade warning should be visible
      const warning = page.locator('.export-warning');
      const warningCount = await warning.count();
      expect(warningCount).toBe(0);

      const downloadPromise = page.waitForEvent('download', { timeout: 30000 });
      await page.locator('.export-modal button.btn-primary').click();
      const download = await downloadPromise;

      const filePath = await download.path();
      expect(filePath).toBeTruthy();
      const content = fs.readFileSync(filePath!, 'utf-8');

      // v3.1.0 export: relationships present + version marker
      expect(content).toMatch(/relationships/);
      expect(content).toMatch(/3\.1\.0/);
    });
  });

  test.describe('Failure', () => {
    test('non-existent contract ID shows error', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);

      await page.goto('/contracts/00000000-0000-0000-0000-000000000000');

      const errorDisplay = page.locator('.error-display');
      await expect(errorDisplay).toBeVisible({ timeout: 30000 });
    });
  });

  test.describe('Edge', () => {
    test('v3.0.2 contract shows empty relationships panel', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);

      await page.goto(`/contracts/${contract302Id}`);
      await page.waitForSelector('.contract-detail-page', { timeout: 30000 });

      // v3.0.2 has no relationships — panel must show empty state
      const panel = page.locator('.relationships-panel');
      await expect(panel).toBeVisible({ timeout: 10000 });

      const empty = page.locator('.relationships-empty');
      await expect(empty).toBeVisible({ timeout: 10000 });
      await expect(empty).toContainText('No relationships');
    });
  });
});
