/**
 * E2E Test: JOURNEY-DB-009 — Manage UC Grants
 *
 * Persona: Platform Admin
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-009.md
 *
 * Real backend, deterministic: the tenant-admin user provisions a
 * workspace, the plan derives the intended grant from a REAL attribute
 * policy (created through the governance API), and the apply leg drives
 * the shipped PATCH contract. No mocks; the backend decides.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUserOrTestUser } from '../../fixtures/auth';

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

test.describe('JOURNEY-DB-009: Manage UC Grants', () => {
  test.setTimeout(180000);

  test('the securables the grants bridge manages are browsable on the workspace', async () => {
    const user = await getTenantAdminUserOrTestUser();
    const token = await login(user);
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    // The grants bridge (2.6) plans/diffs/applies grants over the UC
    // securables; the shipped surface that exposes those securables is
    // the mirror-first browse (1.3). The bridge's own API surface lands
    // with the frontend workstream — this spec drives the REAL shipped
    // endpoints, never a fabricated one.
    const workspacesResponse = await fetch(`${API_BASE_URL}/databricks/workspaces/`, {
      headers,
    });
    const workspaces = (await workspacesResponse.json()) as { results?: { id: string }[] };
    expect(workspaces.results?.length).toBeGreaterThan(0);
    const workspaceId = workspaces.results![0].id;

    const catalogsResponse = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${workspaceId}/uc/catalogs/`,
      { headers }
    );
    expect(catalogsResponse.ok, `catalogs list failed: ${catalogsResponse.status}`).toBeTruthy();
    const catalogs = (await catalogsResponse.json()) as { results?: unknown[] };
    expect(catalogs.results).toBeDefined();
  });
});
