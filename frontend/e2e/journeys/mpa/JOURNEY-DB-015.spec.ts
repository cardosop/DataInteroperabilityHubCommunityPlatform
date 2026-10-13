/**
 * E2E Test: JOURNEY-DB-015 — Set a Databricks Budget
 *
 * Persona: Platform Admin
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-015.md,
 *            docs/mvpdocs/use-cases/UC-DB-015.md
 *
 * Real backend, deterministic: the shipped budget surface is the
 * tenant's budget list (`GET /api/v1/databricks/budgets/` — the 7.6
 * page API with the rolling progress), and the enforcement contract is
 * the live-query dispatch (BLOCK → 429 `WAREHOUSE_COST_BUDGET_EXCEEDED`,
 * zero warehouse work). The 429 leg needs a seeded BLOCK-budget tenant
 * with a LIVE_QUERY asset — `E2E_BUDGET_BLOCK_ASSET_ID` — and follows
 * the W16 environment policy when unseeded. No mocks; the backend
 * decides.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUserOrTestUser } from '../../fixtures/auth';
import { environmentSkipGuard } from '../../fixtures/envPolicy.cjs';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE_URL =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

async function login(user: { email: string; password: string }): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/auth/login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: user.email, password: user.password }),
  });
  expect(response.ok, `login failed: ${response.status}`).toBeTruthy();
  const data = (await response.json()) as { access_token?: string };
  expect(data.access_token).toBeTruthy();
  return data.access_token as string;
}

test.describe('JOURNEY-DB-015: Set a Databricks Budget', () => {
  test.setTimeout(180000);

  test('the tenants budget list carries the rolling progress contract', async () => {
    const user = await getTenantAdminUserOrTestUser();
    const token = await login(user);
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    // The shipped budget page API: the tenant's budget rows with the
    // rolling progress (the 7.6 BudgetViewSet paginated list).
    const response = await fetch(`${API_BASE_URL}/databricks/budgets/`, { headers });
    expect(response.status).toBe(200);
    const body = (await response.json()) as {
      results?: { budget_units_per_hour?: string | null; enforcement_mode?: string }[];
    };
    expect(Array.isArray(body.results)).toBeTruthy();
    for (const row of body.results ?? []) {
      // The landed model contract: an unlimited budget is NULL; the
      // enforcement mode is BLOCK or ALERT (the mode rides the row).
      if (row.budget_units_per_hour != null) {
        expect(Number(row.budget_units_per_hour)).toBeGreaterThan(0);
      }
      expect(['BLOCK', 'ALERT']).toContain(row.enforcement_mode);
    }
  });

  test('the enforcement blocks a BLOCK-mode tenant with 429 and the classified code', async () => {
    const assetId = process.env.E2E_BUDGET_BLOCK_ASSET_ID;
    if (!assetId) {
      environmentSkipGuard(
        'E2E_BUDGET_BLOCK_ASSET_ID unset — the 429 leg needs a seeded BLOCK-budget tenant with a LIVE_QUERY asset',
      );
      test.skip(
        !assetId,
        'seeded BLOCK-budget asset absent — the enforcement contract is covered by the backend journey pins',
      );
      return;
    }

    const user = await getTenantAdminUserOrTestUser();
    const token = await login(user);
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(
      `${API_BASE_URL}/warehouses/query/?asset_id=${assetId}&limit=10`,
      { headers },
    );
    expect(response.status).toBe(429);
    const body = (await response.json()) as { code?: string };
    expect(body.code).toBe('WAREHOUSE_COST_BUDGET_EXCEEDED');
  });
});
