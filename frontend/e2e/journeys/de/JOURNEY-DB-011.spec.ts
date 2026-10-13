/**
 * E2E Test: JOURNEY-DB-011 — Run a Databricks Job
 *
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-011.md
 *
 * Real backend, deterministic: the spec drives the shipped P4 API
 * contract only — the mirror-first jobs listing and the nested runs
 * listing (both paginated, workspace-scoped, zero network on the READ
 * leg), plus the 404 boundary for an unknown job. The mirror rows are
 * provisioned through the API container's Django shell (the 3.7/4.7
 * CLI real-API suite's documented pattern) so the listings run against
 * real rows; no mocks — the backend decides.
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
  // One retry on a transport-level failure: the fetch pool holds a
  // keep-alive connection across the ~15s docker-exec provisioning gap
  // and the API's gunicorn (keepalive=5s) closes it idle server-side —
  // the pooled socket is then reused and reset ("other side closed").
  // The retry opens a fresh connection; the API contract is what the
  // assertions pin, never the connection-reuse behavior.
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/auth/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: user.email, password: user.password }),
    });
  } catch (error) {
    if (!(error instanceof TypeError) || !/fetch failed/.test(error.message)) {
      throw error;
    }
    response = await fetch(`${API_BASE_URL}/auth/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: user.email, password: user.password }),
    });
  }
  expect(response.ok, `login failed: ${response.status}`).toBeTruthy();
  const data = (await response.json()) as { access_token?: string };
  expect(data.access_token, 'login response missing access_token').toBeTruthy();
  return data.access_token as string;
}

interface Provisioned {
  workspace: string;
  job: string;
  email: string;
}

/**
 * A dedicated tenant + workspace + one job mirror row with two run
 * rows, provisioned through the API container's Django shell (the
 * 0.15/3.7 CLI real-API pattern). The journey spec never mutates the
 * shared E2E tenant.
 */
function provisionJob(): Provisioned {
  skipIfRemoteApi(test, 'Job-mirror provisioning requires docker exec');
  const suffix = Math.random().toString(16).slice(2, 10);
  const script = `
import json
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import Tenant, TenantConfig, TenantPlan
from hub.apps.databricks_admin.models import (
    DatabricksCloud, DatabricksWorkspace, DatabricksJob, DatabricksJobRun,
)
from hub.apps.users.models import User, Role, UserRole, UserStatus
tenant = Tenant.objects.create(name='job-e2e-${suffix}', slug='job-e2e-${suffix}')
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
    email='job-e2e-${suffix}@test.com', password='testpass123',
    tenant=tenant, status=UserStatus.ACTIVE,
)
role, _ = Role.objects.get_or_create(tenant=tenant, name='TENANT_ADMIN')
UserRole.objects.get_or_create(user=user, role=role)
workspace = DatabricksWorkspace.objects.create(
    tenant=tenant, name='ws-job-e2e-${suffix}',
    host='dbc-6710eb95-8fe1.cloud.databricks.com',
    cloud=DatabricksCloud.AWS, region='us-east-1', status='ACTIVE',
)
job = DatabricksJob.objects.create(
    workspace=workspace, job_id='job-e2e-${suffix}', name='nightly-etl',
    task_config=[{'task_key': 'etl', 'sql_task': {'warehouse_id': 'wh-e2e-${suffix}'}}],
)
DatabricksJobRun.objects.create(
    job=job, run_id='42', lifecycle_state='RUNNING', result_state='SUCCESS',
    duration_ms=60000,
)
DatabricksJobRun.objects.create(
    job=job, run_id='43', lifecycle_state='TERMINATED', result_state='FAILED',
    duration_ms=120000, error_message='Task etl failed',
)
print(json.dumps({'workspace': str(workspace.id), 'job': job.job_id, 'email': user.email}))
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

test.describe('JOURNEY-DB-011: Run a Databricks Job', () => {
  test.setTimeout(180000);

  test('the mirror-first jobs listing serves the paginated envelope with the seeded job', async () => {
    const provisioned = provisionJob();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspace}/jobs/`,
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
    expect(rows.map((row) => row['job_id'])).toContain(provisioned.job);
    for (const row of rows) {
      expect(typeof row['job_id'], `row shape: ${JSON.stringify(row)}`).toBe('string');
      expect(typeof row['name'], `row shape: ${JSON.stringify(row)}`).toBe('string');
      expect(Array.isArray(row['task_config']), `row shape: ${JSON.stringify(row)}`).toBe(true);
    }
  });

  test('the nested runs listing serves the seeded run rows with their states', async () => {
    const provisioned = provisionJob();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspace}/jobs/${provisioned.job}/runs/`,
      { headers }
    );
    const responseText = await response.text(); // read the body ONCE (the expect message would consume it)
    expect(response.status, `runs list failed: ${responseText}`).toBe(200);
    const envelope = JSON.parse(responseText) as {
      count?: number;
      results?: Record<string, unknown>[];
    };
    expect(Array.isArray(envelope.results), 'the runs list answers the paginated envelope').toBe(
      true
    );
    const rows = envelope.results ?? [];
    expect(rows.map((row) => row['run_id'])).toContain('42');
    for (const row of rows) {
      expect(typeof row['run_id'], `row shape: ${JSON.stringify(row)}`).toBe('string');
      expect(typeof row['lifecycle_state'], `row shape: ${JSON.stringify(row)}`).toBe('string');
      expect(typeof row['duration_ms'], `row shape: ${JSON.stringify(row)}`).toBe('number');
    }
  });

  test('an unknown job surfaces the 404 boundary', async () => {
    const provisioned = provisionJob();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspace}/jobs/job-does-not-exist/runs/`,
      { headers }
    );
    expect(response.status).toBe(404);
  });
});
