/**
 * E2E Test: @critical JOURNEY-DB-007 — Request a UC DDL Change
 *
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-007.md
 *
 * Real backend, deterministic: the spec authenticates the tenant-admin
 * test user, lists the provisioned workspace via the REAL registry, and
 * drives the shipped P2 API contract — create a DDL change request with
 * the truthful preview, then submit it. The 2.4 guards are exercised
 * with a malformed-identifier rejection. No mocks; the backend decides.
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
  expect(data.access_token, 'login response missing access_token').toBeTruthy();
  return data.access_token as string;
}

test.describe('@critical JOURNEY-DB-007: Request a UC DDL Change', () => {
  test.setTimeout(180000);

  test('a draft DDL request carries the truthful preview and submits', async () => {
    const user = await getTenantAdminUserOrTestUser();
    const token = await login(user);
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const workspacesResponse = await fetch(`${API_BASE_URL}/databricks/workspaces/`, { headers });
    expect(
      workspacesResponse.ok,
      `workspaces list failed: ${workspacesResponse.status}`
    ).toBeTruthy();
    const workspaces = (await workspacesResponse.json()) as { results?: { id: string }[] };
    expect(workspaces.results?.length, 'no workspace provisioned for the journey').toBeGreaterThan(
      0
    );
    const workspaceId = workspaces.results![0].id;

    const createResponse = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${workspaceId}/uc/changes/`,
      {
        method: 'POST',
        headers,
        body: JSON.stringify({
          change_type: 'CREATE',
          securable_type: 'TABLE',
          definition: {
            identifiers: ['main', 'sales', 'e2e_orders'],
            options: { table_type: 'MANAGED', columns: [{ name: 'id' }] },
          },
          requires_approval: true,
          required_approval_chain: [{ step: 1, role: 'TENANT_ADMIN', label: 'Admin step' }],
        }),
      }
    );
    // Read the body ONCE — the expect message argument is evaluated
    // eagerly, so `await createResponse.text()` inside it consumed the
    // body and the later `.json()` threw "Body is unusable: Body has
    // already been read".
    const createBodyText = await createResponse.text();
    expect(createResponse.status, `create failed: ${createBodyText}`).toBe(201);
    const draft = JSON.parse(createBodyText) as {
      id: string;
      status: string;
      preview: { kind: string; path: string };
    };
    expect(draft.status).toBe('DRAFT');
    expect(draft.preview.kind).toBe('rest');
    expect(draft.preview.path).toBe('/api/2.1/unity-catalog/tables');

    const submitResponse = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${workspaceId}/uc/changes/${draft.id}/submit/`,
      { method: 'POST', headers }
    );
    // Same read-once pattern as the create call above.
    const submitBodyText = await submitResponse.text();
    expect(submitResponse.status, `submit failed: ${submitBodyText}`).toBe(200);
    const submitted = JSON.parse(submitBodyText) as { status: string };
    expect(submitted.status).toBe('PENDING_APPROVAL');
  });

  test('a malformed identifier is rejected at the boundary', async () => {
    const user = await getTenantAdminUserOrTestUser();
    const token = await login(user);
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const workspacesResponse = await fetch(`${API_BASE_URL}/databricks/workspaces/`, {
      headers,
    });
    const workspaces = (await workspacesResponse.json()) as { results?: { id: string }[] };
    expect(workspaces.results?.length).toBeGreaterThan(0);
    const workspaceId = workspaces.results![0].id;

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${workspaceId}/uc/changes/`,
      {
        method: 'POST',
        headers,
        body: JSON.stringify({
          change_type: 'CREATE',
          securable_type: 'TABLE',
          definition: { identifiers: ['main', 'sales', 'bad;DROP--'], options: {} },
        }),
      }
    );
    expect(response.status).toBe(400);
    const body = (await response.json()) as { code?: string };
    expect(body.code).toBe('DATABRICKS_DDL_INVALID_IDENTIFIER');
  });
});
