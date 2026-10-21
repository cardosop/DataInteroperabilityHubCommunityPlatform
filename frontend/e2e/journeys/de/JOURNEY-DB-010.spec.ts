/**
 * E2E Test: JOURNEY-DB-010 — Manage SQL Warehouses
 *
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-010.md
 *
 * Real backend, deterministic: the spec drives the shipped P3 API
 * contract only — the mirror-first warehouse listing (paginated,
 * workspace-scoped, zero network on the READ leg), the fail-closed
 * identity leg (an action without a Databricks binding answers the
 * masked 502 BEFORE any network call), and the 404 boundary for an
 * unknown warehouse. The mirror row is provisioned through the API
 * container's Django shell (the 3.7 CLI real-API suite's documented
 * pattern) so the listing and the fail-closed leg run against real
 * rows; no mocks — the backend decides.
 */

import { expect, test } from '@playwright/test';
import { execSync } from 'node:child_process';
import { getTenantAdminUserOrTestUser } from '../../fixtures/auth';
import { skipIfRemoteApi } from '../../fixtures/helpers';

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

interface Provisioned {
  workspace: string;
  warehouse: string;
  email: string;
}

/**
 * A dedicated tenant + workspace + one mirror row, provisioned through
 * the API container's Django shell (the 0.15/3.7 CLI real-API
 * pattern). The journey spec never mutates the shared E2E tenant.
 */
function provisionWarehouse(): Provisioned {
  skipIfRemoteApi(test, 'SQL-warehouse mirror provisioning requires docker exec');
  const suffix = Math.random().toString(16).slice(2, 10);
  const script = `
import json
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import Tenant, TenantConfig, TenantPlan
from hub.apps.databricks_admin.models import (
    DatabricksCloud, DatabricksWorkspace, DatabricksSqlWarehouse,
)
from hub.apps.users.models import User, Role, UserRole, UserStatus
tenant = Tenant.objects.create(name='wh-e2e-${suffix}', slug='wh-e2e-${suffix}')
tenant.databricks_control_plane_enabled = True
tenant.save(update_fields=['databricks_control_plane_enabled'])
# The billing middleware gates POST/PATCH/DELETE without an ACTIVE BASE
# subscription — the test helper's activation (TenantConfig + the active
# free plan + a BASE subscription) is mirrored here.
TenantConfig.objects.get_or_create(tenant=tenant)
free_plan = TenantPlan.objects.filter(slug='free', is_active=True).first()
Subscription.objects.create(
    tenant=tenant, plan=free_plan, category='BASE', status=SubscriptionStatus.ACTIVE,
)
user = User.objects.create_user(
    email='wh-e2e-${suffix}@test.com', password='testpass123',
    tenant=tenant, status=UserStatus.ACTIVE,
)
role, _ = Role.objects.get_or_create(tenant=tenant, name='TENANT_ADMIN')
UserRole.objects.get_or_create(user=user, role=role)
workspace = DatabricksWorkspace.objects.create(
    tenant=tenant, name='ws-wh-e2e-${suffix}',
    host='dbc-6710eb95-8fe1.cloud.databricks.com',
    cloud=DatabricksCloud.AWS, region='us-east-1', status='ACTIVE',
)
mirror = DatabricksSqlWarehouse.objects.create(
    workspace=workspace, warehouse_id='wh-e2e-${suffix}', name='analytics',
    state='STOPPED', serverless=True, size=None,
)
print(json.dumps({'workspace': str(workspace.id), 'warehouse': mirror.warehouse_id, 'email': user.email}))
`;
  // The script goes in via STDIN (docker exec -i) — indentation and
  // quoting are preserved exactly; no shell -c collapsing.
  const out = execSync('docker exec -i hub-test-api python hub/manage.py shell', {
    encoding: 'utf-8',
    timeout: 120000,
    input: script,
  });
  const lines = out.split('\n').filter((line) => line.trim().startsWith('{"workspace"'));
  expect(lines.length, `provisioning failed: ${out.slice(0, 400)}`).toBeGreaterThan(0);
  return JSON.parse(lines[0].trim()) as Provisioned;
}

test.describe('JOURNEY-DB-010: Manage SQL Warehouses', () => {
  test.setTimeout(180000);

  test('the mirror-first listing serves the paginated envelope with the seeded fleet', async () => {
    const provisioned = provisionWarehouse();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspace}/sql-warehouses/`,
      { headers }
    );
    const responseText = await response.text(); // read the body ONCE (the expect message would consume it)
    expect(response.status, `list failed: ${responseText}`).toBe(200);
    const envelope = JSON.parse(responseText) as {
      count?: number;
      results?: Record<string, unknown>[];
    };
    expect(Array.isArray(envelope.results), 'the list answers the paginated envelope').toBe(true);
    const rows = envelope.results ?? [];
    expect(rows.map((row) => row['warehouse_id'])).toContain(provisioned.warehouse);
    for (const row of rows) {
      expect(typeof row['warehouse_id'], `row shape: ${JSON.stringify(row)}`).toBe('string');
      expect(typeof row['state'], `row shape: ${JSON.stringify(row)}`).toBe('string');
      expect(typeof row['serverless'], `row shape: ${JSON.stringify(row)}`).toBe('boolean');
    }
  });

  test('a lifecycle action fails closed without a Databricks binding', async () => {
    const provisioned = provisionWarehouse();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    // No DatabricksUserBinding exists for this user — the D12 identity
    // leg refuses BEFORE any network call, deterministically.
    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspace}/sql-warehouses/${provisioned.warehouse}/start/`,
      { method: 'POST', headers }
    );
    const responseText = await response.text(); // read the body ONCE (the expect message would consume it)
    expect(response.status, `start failed: ${responseText}`).toBe(502);
    const body = JSON.parse(responseText) as { code?: string };
    expect(body.code).toBe('DATABRICKS_OBO_REFRESH_FAILED');
  });

  test('an unknown warehouse surfaces the 404 boundary', async () => {
    const user = await getTenantAdminUserOrTestUser();
    const token = await login(user);
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const workspacesResponse = await fetch(`${API_BASE_URL}/databricks/workspaces/`, {
      headers,
    });
    expect(
      workspacesResponse.ok,
      `workspaces list failed: ${workspacesResponse.status}`
    ).toBeTruthy();
    const workspaces = (await workspacesResponse.json()) as { results?: { id: string }[] };
    expect(workspaces.results?.length, 'no workspace provisioned for the journey').toBeGreaterThan(
      0
    );
    const workspaceId = workspaces.results![0].id;

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${workspaceId}/sql-warehouses/wh-does-not-exist/start/`,
      { method: 'POST', headers }
    );
    expect(response.status).toBe(404);
  });
});
