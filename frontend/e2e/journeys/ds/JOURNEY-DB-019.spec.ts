/**
 * E2E Test: JOURNEY-DB-019 — Register a Model in Unity Catalog
 *
 * Persona: Data Scientist
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-019.md
 *
 * Real backend, deterministic: the spec drives the shipped P12 API
 * contract only — the SAME surface the ML-assets page rides. Every leg
 * is fail-closed or mirror-first, so the backend decides with ZERO
 * live-Databricks network calls:
 *
 * - the flag-off tenant answers the classified 403
 *   (DATABRICKS_ML_ASSETS_DISABLED) before anything else,
 * - the mirror-first listings serve the seeded model (with its
 *   reported aliases), the tagged feature table, and the serving
 *   endpoint (paginated, workspace-scoped, zero network on the READ
 *   legs),
 * - a malformed register (a two-part full_name) answers the
 *   classified 400 DATABRICKS_ML_INVALID_FULL_NAME with zero API calls,
 * - a version log on an unknown mirror row answers the classified 404
 *   DATABRICKS_UC_OBJECT_NOT_FOUND (the UC-DB-019 error table) with
 *   zero API calls.
 *
 * The register → version-log → alias-set round-trip with REAL
 * workspace calls is proven by the backend journey pins
 * (hub/apps/databricks_admin/tests/test_ml_assets_journeys.py — the
 * no-mocks discipline; the workspace API is unreachable from the E2E
 * network, so the round-trip legs stay there rather than flaking here).
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
  modelName: string;
  modelFullName: string;
  alias: string;
  featureTable: string;
  servingEndpoint: string;
}

/**
 * Two dedicated tenants (flagged + flag-off) + one workspace each +
 * the mirror rows on the flagged tenant (model with an alias, a
 * feature_store-tagged table, a serving endpoint), provisioned through
 * the API container's Django shell (the 0.15/3.7 CLI real-API
 * pattern). The journey spec never mutates the shared E2E tenant.
 */
/**
 * True when the hub-test-api container is running (and healthy when a
 * healthcheck exists). Used to gate the docker exec below.
 */
function isApiContainerHealthy(): boolean {
  try {
    const out = execSync(
      'docker inspect -f "{{.State.Running}} {{.State.Health.Status}}" hub-test-api',
      { encoding: 'utf-8', timeout: 5000 }
    ).trim();
    return /^true( healthy)?$/.test(out);
  } catch {
    return false;
  }
}

/** Bounded poll until the API container reports healthy. */
async function waitForApiContainerHealthy(maxWaitMs: number): Promise<void> {
  const deadline = Date.now() + maxWaitMs;
  while (!isApiContainerHealthy() && Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 5000));
  }
}

/**
 * Run the provisioning script in the API container with a bounded
 * retry for container restarts: the batch wrapper + fix recreations
 * bounce ``hub-test-api`` with ``--force-recreate`` mid-run, and a
 * docker exec landing in that window either fails instantly with
 * "container … is not running" or — worse — is killed MID-EXECUTION
 * (b6 JOURNEY-DB-019: the exec died 2s into Django startup with no
 * docker error message, and the next attempt hit the not-running
 * window). Both shapes are transient stack churn, so they retry;
 * a Python traceback means the script itself failed and rethrows
 * immediately. The health gate keeps attempts out of the boot
 * window and the whole loop stays inside the 180s test budget.
 */
async function runProvisionScript(script: string): Promise<string> {
  const maxAttempts = 4;
  let lastErr: unknown;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    if (!isApiContainerHealthy()) {
      await waitForApiContainerHealthy(attempt === 0 ? 30000 : 15000);
    }
    try {
      const out = execSync('docker exec -i hub-test-api python hub/manage.py shell', {
        encoding: 'utf-8',
        timeout: 120000,
        maxBuffer: 16 * 1024 * 1024,
        input: script,
      });
      // The provisioning script ends with the JSON payload — its
      // presence proves the shell ran to completion.
      if (out.includes('"workspace"')) return out;
      lastErr = new Error('provisioning output missing from shell output');
    } catch (err) {
      lastErr = err;
    }
    const msg = lastErr instanceof Error ? lastErr.message : String(lastErr);
    if (/Traceback \(most recent call last\)/i.test(msg)) throw lastErr;
    const transient =
      /is not running|No such container|Command failed|missing from shell output/i.test(msg);
    if (!transient || attempt === maxAttempts - 1) throw lastErr;
    // intentional: best-effort settle wait for the recreated container; the final attempt must pass or the test fails with the original docker error.
    await new Promise((r) => setTimeout(r, 10000));
  }
  throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
}

async function provisionMlAssets(): Promise<Provisioned> {
  skipIfRemoteApi(test, 'ML-asset mirror provisioning requires docker exec');
  const suffix = Math.random().toString(16).slice(2, 10);
  const script = `
import json
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import Tenant, TenantConfig, TenantPlan
from hub.apps.databricks_admin.models import (
    DatabricksCloud, DatabricksWorkspace, UCCatalog, UCSchema, UCModel,
    UCTable, DatabricksMlServingEndpoint,
)
from hub.apps.users.models import User, Role, UserRole, UserStatus

def make_tenant(name, ml_enabled):
    tenant = Tenant.objects.create(name=name, slug=name)
    tenant.databricks_control_plane_enabled = True
    tenant.databricks_ml_assets_enabled = ml_enabled
    tenant.save(update_fields=[
        'databricks_control_plane_enabled', 'databricks_ml_assets_enabled',
    ])
    # The billing middleware gates POST/PATCH/DELETE without an ACTIVE BASE
    # subscription — the test helper's activation is mirrored here.
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

flagged = make_tenant('ml-e2e-${suffix}', ml_enabled=True)
unflagged = make_tenant('ml-off-e2e-${suffix}', ml_enabled=False)
user = make_user(flagged, 'ml-e2e-${suffix}@test.com')
user_off = make_user(unflagged, 'ml-off-e2e-${suffix}@test.com')
workspace = make_workspace(flagged, 'ws-ml-e2e-${suffix}')
workspace_off = make_workspace(unflagged, 'ws-ml-off-e2e-${suffix}')

catalog = UCCatalog.objects.create(workspace=workspace, name='ml_catalog')
schema = UCSchema.objects.create(catalog=catalog, name='ml_schema')
model = UCModel.objects.create(
    schema=schema, name='churn_model',
    full_name='ml_catalog.ml_schema.churn_model',
    aliases=[{'alias_name': 'champion', 'version_num': 3}],
    latest_version=3,
)
table = UCTable.objects.create(
    schema=schema, name='churn_features',
    full_name='ml_catalog.ml_schema.churn_features',
    tags=[{'key': 'feature_store', 'value': 'true'}],
)
endpoint = DatabricksMlServingEndpoint.objects.create(
    workspace=workspace, endpoint_type='SERVING', name='ep-e2e-${suffix}',
    state='READY',
)

print(json.dumps({
    'workspace': str(workspace.id),
    'workspaceFlagOff': str(workspace_off.id),
    'email': user.email,
    'emailFlagOff': user_off.email,
    'modelName': model.name,
    'modelFullName': model.full_name,
    'alias': 'champion',
    'featureTable': table.name,
    'servingEndpoint': endpoint.name,
}))
`;
  // The script goes in via STDIN (docker exec -i) — indentation and
  // quoting are preserved exactly; no shell -c collapsing.
  const out = await runProvisionScript(script);
  const lines = out.split('\n').filter((line) => line.trim().startsWith('{"workspace"'));
  expect(lines.length, `provisioning failed: ${out.slice(0, 400)}`).toBeGreaterThan(0);
  return JSON.parse(lines[0].trim()) as Provisioned;
}

test.describe('JOURNEY-DB-019: Register a Model in Unity Catalog', () => {
  test.setTimeout(180000);

  test('the flag-off tenant answers the classified 403', async () => {
    const provisioned = await provisionMlAssets();
    const token = await login({ email: provisioned.emailFlagOff, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspaceFlagOff}/ml-assets/models/`,
      { headers }
    );
    const responseText = await response.text(); // read the body ONCE (the expect message would consume it)
    expect(response.status, `list failed: ${responseText}`).toBe(403);
    const body = JSON.parse(responseText) as { error?: { code?: string } };
    expect(body.error?.code).toBe('DATABRICKS_ML_ASSETS_DISABLED');
  });

  test('the mirror-first model listing serves the seeded model with its reported aliases', async () => {
    const provisioned = await provisionMlAssets();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspace}/ml-assets/models/`,
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
    expect(rows.map((row) => row['name'])).toContain(provisioned.modelName);
    const model = rows.find((row) => row['name'] === provisioned.modelName);
    expect(model?.['full_name']).toBe(provisioned.modelFullName);
    expect(model?.['latest_version']).toBe(3);
    expect(model?.['aliases']).toEqual([{ alias_name: 'champion', version_num: 3 }]);
  });

  test('the feature-table listing serves the tagged table mirror-derived', async () => {
    const provisioned = await provisionMlAssets();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspace}/ml-assets/feature-tables/`,
      { headers }
    );
    const responseText = await response.text(); // read the body ONCE (the expect message would consume it)
    expect(response.status, `list failed: ${responseText}`).toBe(200);
    const envelope = JSON.parse(responseText) as {
      count?: number;
      results?: Record<string, unknown>[];
    };
    const rows = envelope.results ?? [];
    expect(rows.map((row) => row['name'])).toContain(provisioned.featureTable);
    const table = rows.find((row) => row['name'] === provisioned.featureTable);
    expect(table?.['tags']).toEqual([{ key: 'feature_store', value: 'true' }]);
  });

  test('the serving-endpoint listing serves the seeded mirror row', async () => {
    const provisioned = await provisionMlAssets();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspace}/ml-assets/serving-endpoints/`,
      { headers }
    );
    const responseText = await response.text(); // read the body ONCE (the expect message would consume it)
    expect(response.status, `list failed: ${responseText}`).toBe(200);
    const envelope = JSON.parse(responseText) as {
      count?: number;
      results?: Record<string, unknown>[];
    };
    const rows = envelope.results ?? [];
    expect(rows.map((row) => row['name'])).toContain(provisioned.servingEndpoint);
    const endpoint = rows.find((row) => row['name'] === provisioned.servingEndpoint);
    expect(endpoint?.['endpoint_type']).toBe('SERVING');
    expect(endpoint?.['state']).toBe('READY');
  });

  test('a malformed register answers the classified 400 with zero API calls', async () => {
    const provisioned = await provisionMlAssets();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspace}/ml-assets/models/`,
      {
        method: 'POST',
        headers,
        body: JSON.stringify({ full_name: 'only_two.parts' }),
      }
    );
    const responseText = await response.text(); // read the body ONCE (the expect message would consume it)
    expect(response.status, `register failed: ${responseText}`).toBe(400);
    const body = JSON.parse(responseText) as { error?: { code?: string } };
    expect(body.error?.code).toBe('DATABRICKS_ML_INVALID_FULL_NAME');
  });

  test('a version log on an unknown model answers the classified 404', async () => {
    const provisioned = await provisionMlAssets();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const unknownId = '00000000-0000-0000-0000-000000000000';
    const response = await fetch(
      `${API_BASE_URL}/databricks/workspaces/${provisioned.workspace}/ml-assets/models/${unknownId}/versions/`,
      {
        method: 'POST',
        headers,
        body: JSON.stringify({ source: 'dbfs:/ml/churn' }),
      }
    );
    const responseText = await response.text(); // read the body ONCE (the expect message would consume it)
    expect(response.status, `version log failed: ${responseText}`).toBe(404);
    const body = JSON.parse(responseText) as { error?: { code?: string } };
    expect(body.error?.code).toBe('DATABRICKS_UC_OBJECT_NOT_FOUND');
  });
});
