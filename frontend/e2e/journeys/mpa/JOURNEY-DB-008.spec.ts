/**
 * E2E Test: @critical JOURNEY-DB-008 — Approve or Reject a DDL Change
 *
 * Persona: Platform Admin
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-008.md
 *
 * Real backend, deterministic: the tenant-admin user requests a change,
 * submits it, sees it in the REAL approver inbox (the workflow's step
 * authorization decides visibility), and approves it — the shipped P2
 * contract end to end. No mocks; the backend decides.
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

test.describe('@critical JOURNEY-DB-008: Approve or Reject a DDL Change', () => {
  test.setTimeout(180000);

  test('the approver inbox surfaces the pending request and approval resolves it', async () => {
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
    const draft = (await createResponse.json()) as { id: string };

    await fetch(
      `${API_BASE_URL}/databricks/workspaces/${workspaceId}/uc/changes/${draft.id}/submit/`,
      { method: 'POST', headers }
    );

    const inboxResponse = await fetch(`${API_BASE_URL}/databricks/uc/changes/pending-approvals/`, {
      headers,
    });
    expect(inboxResponse.ok, `inbox failed: ${inboxResponse.status}`).toBeTruthy();
    const inbox = (await inboxResponse.json()) as { results?: { id: string }[] };
    expect(inbox.results?.map((row) => row.id)).toContain(draft.id);

    const approveResponse = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${workspaceId}/uc/changes/${draft.id}/approve/`,
      { method: 'POST', headers }
    );
    expect(approveResponse.status, `approve failed: ${await approveResponse.text()}`).toBe(200);
    const approved = (await approveResponse.json()) as { status: string };
    expect(approved.status).toBe('APPROVED');
  });
});
