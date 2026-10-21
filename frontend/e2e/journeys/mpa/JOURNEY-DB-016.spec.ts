/**
 * E2E Test: JOURNEY-DB-016 — Provision a Workspace from the Account
 *
 * Persona: Platform Admin
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-016.md,
 *            docs/mvpdocs/use-cases/UC-DB-016.md
 *
 * Real backend, deterministic: the shipped account-plane read surface is
 * the cross-tenant estate summary (`GET /api/v1/databricks/estate-summary/`
 * — the 8.4 admin-DB aggregate) — platform-admin-only, so a platform admin
 * sees the paginated estate rows with the landed shape, and a tenant admin
 * gets the prose error table's 403 PERMISSION_DENIED. The provisioning
 * write path needs an account link + flag + signoff (seeded fixtures), so
 * its contract is covered by the backend journey pins; this spec pins the
 * RBAC + shape contract every environment can prove. No mocks; the
 * backend decides.
 */

import { expect, test } from '@playwright/test';
import { getPlatformAdminUser, getTenantAdminUserOrTestUser } from '../../fixtures/auth';

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

test.describe('JOURNEY-DB-016: Provision a Workspace from the Account', () => {
  test.setTimeout(180000);

  test('the platform admin sees the estate summary with the landed row shape', async () => {
    const user = await getPlatformAdminUser();
    const token = await login(user);
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(`${API_BASE_URL}/databricks/estate-summary/`, { headers });
    expect(response.status).toBe(200);
    const body = (await response.json()) as {
      results?: {
        tenant_id?: string;
        tenant_name?: string;
        workspace_count?: number;
        workspaces_by_state?: Record<string, number>;
        budget_count?: number;
        block_budgets?: number;
        alert_budgets?: number;
      }[];
    };
    expect(Array.isArray(body.results)).toBeTruthy();
    for (const row of body.results ?? []) {
      // The landed 8.4 aggregate row: identity + per-state workspace
      // counts + budget figures, all derived (never cached).
      expect(typeof row.tenant_id).toBe('string');
      expect(typeof row.tenant_name).toBe('string');
      expect(typeof row.workspace_count).toBe('number');
      expect(row.workspaces_by_state).toBeTruthy();
      expect(typeof row.budget_count).toBe('number');
      expect(typeof row.block_budgets).toBe('number');
      expect(typeof row.alert_budgets).toBe('number');
    }
  });

  test('a tenant admin gets the prose 403 PERMISSION_DENIED', async () => {
    const user = await getTenantAdminUserOrTestUser();
    const token = await login(user);
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(`${API_BASE_URL}/databricks/estate-summary/`, { headers });
    expect(response.status).toBe(403);
    const body = (await response.json()) as { error?: { code?: string } };
    expect(body.error?.code).toBe('PERMISSION_DENIED');
  });
});
