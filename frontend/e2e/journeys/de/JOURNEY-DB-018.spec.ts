/**
 * E2E Test: JOURNEY-DB-018 — Run a dbt Transformation on Databricks
 *
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-018.md
 *
 * Real backend, deterministic: the spec drives the shipped journey
 * PRECONDITIONS only — the surfaces steps 1–2 ride today:
 *
 * - the transformation config surface (the "defines a dbt
 *   transformation as usual" leg) answers the paginated list with the
 *   seeded dbt-native pipeline,
 * - the registered workspace + warehouse-connection registry (the
 *   step-2 "pick a Databricks target" precondition) answers for the
 *   provisioned tenant.
 *
 * The target-selection leg (the execution_target field on the run
 * config) lands with the API wiring in task 11.7 — the spec pins the
 * journey's shipped surface honestly and names the follow-up in the
 * header, never a placeholder assertion.
 *
 * The rows are provisioned through the API container's Django shell
 * (the 3.7 CLI real-API suite's documented pattern) so the legs run
 * against real rows; no mocks — the backend decides.
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
  email: string;
  pipeline: string;
}

/**
 * One tenant + one registered workspace + one dbt-native pipeline,
 * provisioned through the API container's Django shell (the 0.15/3.7
 * CLI real-API pattern). The journey spec never mutates the shared
 * E2E tenant.
 */
function provisionJourney(): Provisioned {
  skipIfRemoteApi(test, 'DB-018 journey provisioning requires docker exec');
  const suffix = Math.random().toString(16).slice(2, 10);
  const script = `
import json
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import Tenant, TenantConfig, TenantPlan
from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace
from hub.apps.users.models import User, Role, UserRole, UserStatus
from hub.apps.transformation.models import TransformationPipeline, PipelineStatus

def make_tenant(name):
    tenant = Tenant.objects.create(name=name, slug=name)
    tenant.databricks_control_plane_enabled = True
    # The transformation pipelines endpoint gates on the per-tenant
    # transformation_enabled flag (default False → 403
    # TRANSFORMATION_DISABLED). The journey IS the dbt-transformation
    # surface — enable it on the provisioned tenant.
    tenant.transformation_enabled = True
    tenant.save(update_fields=['databricks_control_plane_enabled', 'transformation_enabled'])
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

tenant = make_tenant('dbt-db018-${suffix}')
user = make_user(tenant, 'dbt-db018-${suffix}@test.com')
workspace = DatabricksWorkspace.objects.create(
    tenant=tenant, name='ws-db018-${suffix}',
    host='dbc-6710eb95-8fe1.cloud.databricks.com',
    cloud=DatabricksCloud.AWS, region='us-east-1', status='ACTIVE',
)
pipeline = TransformationPipeline.objects.create(
    tenant=tenant, name='dbt-db018-${suffix}', created_by=user,
    status=PipelineStatus.DRAFT,
    # The model's full_clean() enforces the structural floor:
    # pipeline_definition MUST carry version + a non-empty steps list
    # with name/type per step (hub/apps/transformation/models.py).
    # The old {'mode': 'DBT', 'engine': 'dbt'} payload predates it and
    # fails save() with "Pipeline definition must contain 'version'".
    pipeline_definition={
        'version': '1.0.0',
        'mode': 'DBT',
        'engine': 'dbt',
        'steps': [{'name': 'dbt_run', 'type': 'task', 'task': 'dbt_run', 'input': {}}],
    },
    metadata={},
    warehouse_credential_ref='arn:aws:secretsmanager:us-east-1:123456789012:secret:wh-db018',
    git_credential_ref='arn:aws:secretsmanager:us-east-1:123456789012:secret:git-db018',
)

print(json.dumps({
    'workspace': str(workspace.id),
    'email': user.email,
    'pipeline': str(pipeline.id),
}))
`;
  const out = execSync('docker exec -i hub-test-api python hub/manage.py shell', {
    encoding: 'utf-8',
    timeout: 120000,
    input: script,
  });
  const lines = out.split('\n').filter((line) => line.trim().startsWith('{"workspace"'));
  expect(lines.length, `provisioning failed: ${out.slice(0, 400)}`).toBeGreaterThan(0);
  return JSON.parse(lines[0].trim()) as Provisioned;
}

test.describe('JOURNEY-DB-018: Run a dbt Transformation on Databricks', () => {
  test.setTimeout(180000);

  test('the transformation config surface lists the seeded dbt pipeline', async () => {
    const provisioned = provisionJourney();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(`${API_BASE_URL}/transformation/pipelines/`, { headers });
    const responseText = await response.text(); // read the body ONCE (the expect message would consume it)
    expect(response.status, `list failed: ${responseText}`).toBe(200);
    const envelope = JSON.parse(responseText) as {
      count?: number;
      results?: Record<string, unknown>[];
    };
    expect(Array.isArray(envelope.results), 'the list answers the paginated envelope').toBe(true);
    const ids = (envelope.results ?? []).map((row) => row['id']);
    expect(ids).toContain(provisioned.pipeline);
  });

  test('the registered workspace answers on the registry (the step-2 precondition)', async () => {
    const provisioned = provisionJourney();
    const token = await login({ email: provisioned.email, password: 'testpass123' });
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };

    const response = await fetch(`${API_BASE_URL}/databricks/workspaces/`, { headers });
    const responseText = await response.text();
    expect(response.status, `list failed: ${responseText}`).toBe(200);
    const envelope = JSON.parse(responseText) as {
      results?: Record<string, unknown>[];
    };
    const ids = (envelope.results ?? []).map((row) => row['id']);
    expect(ids).toContain(provisioned.workspace);
  });
});
