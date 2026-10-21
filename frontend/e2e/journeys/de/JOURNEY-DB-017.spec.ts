/**
 * E2E Test: JOURNEY-DB-017 — Manage a DLT Pipeline
 *
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-017.md
 *
 * Real backend, deterministic: the spec drives the shipped P10 API
 * contract only — the SAME surface the DLT page (U5) and the `dlt`
 * CLI ride. Every leg is fail-closed or mirror-first, so the backend
 * decides with ZERO live-Databricks network calls:
 *
 * - the flag-off tenant answers the classified 403
 *   (DATABRICKS_DLT_PIPELINES_DISABLED) before anything else,
 * - the mirror-first listing serves the seeded pipelines with their
 *   latest update states (paginated, workspace-scoped, zero network
 *   on the READ leg),
 * - the `databricks.dlt.create` chain refusal (a setting outside the
 *   allowlist) answers the classified 400 with zero API calls,
 * - the conflict gate fails fast — a second start while the mirror
 *   reports a RUNNING update answers 409 DATABRICKS_DLT_UPDATE_CONFLICT
 *   with zero API calls,
 * - stop on an IDLE pipeline is a no-op (stopped:false, reason idle)
 *   with zero API calls.
 *
 * The mirror rows are provisioned through the API container's Django
 * shell (the 3.7 CLI real-API suite's documented pattern) so the legs
 * run against real rows; no mocks — the backend decides.
 */

import { expect, test } from '@playwright/test';
import { execSync } from 'node:child_process';
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
  workspaceFlagOff: string;
  email: string;
  emailFlagOff: string;
  idlePipeline: string;
  activePipeline: string;
}

/**
 * Two dedicated tenants (flagged + flag-off) + one workspace each +
 * two mirror rows on the flagged tenant, provisioned through the API
 * container's Django shell (the 0.15/3.7 CLI real-API pattern). The
 * journey spec never mutates the shared E2E tenant.
 */
function provisionPipelines(): Provisioned {
  skipIfRemoteApi(test, 'DLT-pipeline mirror provisioning requires docker exec');
  const suffix = Math.random().toString(16).slice(2, 10);
  const script = `
import json
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import Tenant, TenantConfig, TenantPlan
from hub.apps.databricks_admin.models import (
    DatabricksCloud, DatabricksWorkspace, DatabricksDltPipeline,
    DatabricksDltPipelineUpdate,
)
from hub.apps.users.models import User, Role, UserRole, UserStatus

def make_tenant(name, dlt_enabled):
    tenant = Tenant.objects.create(name=name, slug=name)
    tenant.databricks_control_plane_enabled = True
    tenant.databricks_dlt_pipelines_enabled = dlt_enabled
    tenant.save(update_fields=[
        'databricks_control_plane_enabled', 'databricks_dlt_pipelines_enabled',
    ])
    # The billing middleware gates POST/PATCH/DELETE without an ACTIVE BASE
    # subscription — the test helper's activation (TenantConfig + the active
    # free plan + a BASE subscription) is mirrored here.
    TenantConfig.objects.get_or_create(tenant=tenant)
    free_plan = TenantPlan.objects.filter(slug='free', is_active=True).first()
    Subscription.objects.create(
        tenant=tenant, plan=free_plan, category='BASE', status=SubscriptionStatus.ACTIVE,
    )
    return tenant

def make_user(tenant, email):
    user = User.objects.create_user(
        email=email, password='testpass123', tenant=tenant, status=UserStatus.ACTIVE,
    )
    role, _ = Role.objects.get_or_create(tenant=tenant, name='TENANT_ADMIN')
    UserRole.objects.get_or_create(user=user, role=role)
    return user

def make_workspace(tenant, name):
    return DatabricksWorkspace.objects.create(
        tenant=tenant, name=name,
        host='dbc-6710eb95-8fe1.cloud.databricks.com',
        cloud=DatabricksCloud.AWS, region='us-east-1', status='ACTIVE',
    )

flagged = make_tenant('dlt-e2e-${suffix}', dlt_enabled=True)
unflagged = make_tenant('dlt-off-e2e-${suffix}', dlt_enabled=False)
user = make_user(flagged, 'dlt-e2e-${suffix}@test.com')
user_off = make_user(unflagged, 'dlt-off-e2e-${suffix}@test.com')
workspace = make_workspace(flagged, 'ws-dlt-e2e-${suffix}')
workspace_off = make_workspace(unflagged, 'ws-dlt-off-e2e-${suffix}')

# The IDLE pipeline carries a COMPLETED update (latest-update resolution);
# the ACTIVE pipeline carries a RUNNING update (the conflict-gate leg).
idle = DatabricksDltPipeline.objects.create(
    workspace=workspace, pipeline_id='dlt-idle-${suffix}', name='nightly-dlt',
    state='IDLE', channel='CURRENT',
)
DatabricksDltPipelineUpdate.objects.create(
    pipeline=idle, update_id='dlt-upd-${suffix}', state='COMPLETED',
)
active = DatabricksDltPipeline.objects.create(
    workspace=workspace, pipeline_id='dlt-active-${suffix}', name='hourly-dlt',
    state='ACTIVE', channel='CURRENT',
)
DatabricksDltPipelineUpdate.objects.create(
    pipeline=active, update_id='dlt-run-${suffix}', state='RUNNING',
)

print(json.dumps({
    'workspace': str(workspace.id),
    'workspaceFlagOff': str(workspace_off.id),
    'email': user.email,
    'emailFlagOff': user_off.email,
    'idlePipeline': idle.pipeline_id,
    'activePipeline': active.pipeline_id,
}))
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

test.describe('JOURNEY-DB-017: Manage a DLT Pipeline', () => {
  test.setTimeout(180000);

  test('the flag-off tenant answers the classified 403', async () => {
    const provisioned = provisionPipelines();
    const token = await login({ email: provisioned.emailFlagOff, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspaceFlagOff}/dlt-pipelines/`,
      { headers }
    );
    const responseText = await response.text(); // read the body ONCE (the expect message would consume it)
    expect(response.status, `list failed: ${responseText}`).toBe(403);
    const body = JSON.parse(responseText) as { error?: { code?: string } };
    expect(body.error?.code).toBe('DATABRICKS_DLT_PIPELINES_DISABLED');
  });

  test('the mirror-first listing serves the seeded pipelines with latest update states', async () => {
    const provisioned = provisionPipelines();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspace}/dlt-pipelines/`,
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
    expect(rows.map((row) => row['pipeline_id'])).toContain(provisioned.idlePipeline);
    expect(rows.map((row) => row['pipeline_id'])).toContain(provisioned.activePipeline);
    for (const row of rows) {
      expect(typeof row['pipeline_id'], `row shape: ${JSON.stringify(row)}`).toBe('string');
      expect(typeof row['name'], `row shape: ${JSON.stringify(row)}`).toBe('string');
      expect(typeof row['state'], `row shape: ${JSON.stringify(row)}`).toBe('string');
    }
    const idle = rows.find((row) => row['pipeline_id'] === provisioned.idlePipeline);
    const active = rows.find((row) => row['pipeline_id'] === provisioned.activePipeline);
    expect(idle?.['latest_update_state'], 'the latest update resolves mirror-first').toBe(
      'COMPLETED'
    );
    expect(active?.['latest_update_state']).toBe('RUNNING');
  });

  test('a setting outside the allowlist is refused by the chain with the classified 400', async () => {
    const provisioned = provisionPipelines();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspace}/dlt-pipelines/`,
      {
        method: 'POST',
        headers,
        body: JSON.stringify({
          name: 'chain-refused-dlt',
          channel: 'CURRENT',
          clusters: [{ label: 'default', num_workers: 0, policy_id: 'pol-1' }],
          serverless: true,
        }),
      }
    );
    const responseText = await response.text(); // read the body ONCE (the expect message would consume it)
    expect(response.status, `create failed: ${responseText}`).toBe(400);
    const body = JSON.parse(responseText) as { error?: { code?: string; message?: string } };
    expect(body.error?.code).toBe('DATABRICKS_DLT_SETTING_FORBIDDEN');
    expect(body.error?.message ?? '').toContain('serverless');
  });

  test('a second start while an update is active conflicts with the classified 409', async () => {
    const provisioned = provisionPipelines();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspace}/dlt-pipelines/${provisioned.activePipeline}/start/`,
      {
        method: 'POST',
        headers,
        body: JSON.stringify({ full_refresh: true }),
      }
    );
    const responseText = await response.text(); // read the body ONCE (the expect message would consume it)
    expect(response.status, `start failed: ${responseText}`).toBe(409);
    const body = JSON.parse(responseText) as { error?: { code?: string } };
    expect(body.error?.code).toBe('DATABRICKS_DLT_UPDATE_CONFLICT');
  });

  test('stop on an IDLE pipeline is a no-op with zero API calls', async () => {
    const provisioned = provisionPipelines();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspace}/dlt-pipelines/${provisioned.idlePipeline}/stop/`,
      { method: 'POST', headers }
    );
    const responseText = await response.text(); // read the body ONCE (the expect message would consume it)
    expect(response.status, `stop failed: ${responseText}`).toBe(200);
    const body = JSON.parse(responseText) as { stopped?: boolean; reason?: string };
    expect(body.stopped).toBe(false);
    expect(body.reason).toBe('idle');
  });
});
