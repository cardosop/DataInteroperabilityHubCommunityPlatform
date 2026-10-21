/**
 * E2E Test: JOURNEY-DB-013 — Export a Dataset to Databricks
 *
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-013.md
 *
 * Real backend, deterministic: the spec drives the shipped P6 export
 * spine through the REAL trigger dispatch — the preflight passes on the
 * empty scope, the managed-volume staging target resolves from the
 * destination config, and the scoped-write-credential gate refuses the
 * run fail-closed (`DLT_CREDENTIAL_NOT_RESOLVED` — the provisioned
 * export carries no credential material and the API container has no
 * `~/.dlt/secrets.toml`; the provisioning script asserts that state so
 * the refusal is guaranteed, never environment-dependent). The tenant +
 * export row are provisioned through the API container's Django shell
 * (the 3.7 CLI real-API pattern); no mocks — the backend decides.
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

/**
 * One retry on a transport-level failure: the fetch pool holds a
 * keep-alive connection across the ~15s docker-exec provisioning gap
 * and the API's gunicorn (keepalive=5s) closes it idle server-side —
 * the pooled socket is then reused and reset ("other side closed").
 * The retry opens a fresh connection; the API contract is what the
 * assertions pin, never the connection-reuse behavior.
 */
async function fetchWithRetry(url: string, init?: RequestInit): Promise<Response> {
  // globalThis.fetch — never the helper itself (a blanket rename of the
  // call sites must not recurse into this function).
  try {
    return await globalThis.fetch(url, init);
  } catch (error) {
    if (!(error instanceof TypeError) || !/fetch failed/.test(error.message)) {
      throw error;
    }
    return globalThis.fetch(url, init);
  }
}

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
  exportId: string;
  email: string;
  password: string;
}

/**
 * A dedicated tenant (data_movement_enabled) + subscription + tenant
 * admin + one DATABRICKS_TABLE export WITHOUT credential material,
 * provisioned through the API container's Django shell. The credential
 * gate's refusal is deterministic: the container carries no
 * ~/.dlt/secrets.toml (asserted by the provisioning script itself).
 */
function provisionExport(): Provisioned {
  skipIfRemoteApi(test, 'Export provisioning requires docker exec');
  const suffix = Math.random().toString(16).slice(2, 10);
  const script = `
import json
import uuid
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import Tenant, TenantConfig, TenantPlan
from hub.apps.scheduled_export.models import ScheduledExport
from hub.apps.users.models import User, UserStatus
import os

assert not os.path.exists(os.path.expanduser("~/.dlt/secrets.toml")), \\
    "the credential-gate refusal depends on the container carrying no dlt secrets"

tenant = Tenant.objects.create(
    name='export-e2e-${suffix}', slug='export-e2e-${suffix}',
    data_movement_enabled=True,
)
TenantConfig.objects.get_or_create(tenant=tenant)
free_plan = TenantPlan.objects.filter(slug='free', is_active=True).first()
if free_plan:
    Subscription.objects.get_or_create(
        tenant=tenant,
        plan=free_plan,
        defaults={'status': SubscriptionStatus.ACTIVE},
    )
user = User.objects.create_user(
    email='export-e2e-${suffix}@meshant.test',
    password='export-pass-${suffix}',
    tenant=tenant,
    status=UserStatus.ACTIVE,
)
export = ScheduledExport.objects.create(
    tenant=tenant,
    name='export-e2e-${suffix}',
    destination_type='DATABRICKS_TABLE',
    destination_config={
        'host': 'dbc-abc.cloud.databricks.com',
        'http_path': '/sql/1.0/warehouses/abc123',
        'catalog': 'meshant',
        'schema': 'staging',
    },
    source_scope={'file_ids': [str(uuid.uuid4())]},
    schedule_config={'cron': '0 3 * * *'},
)
print(json.dumps({
    'export_id': str(export.id),
    'email': user.email,
    'password': 'export-pass-${suffix}',
}))
`;
  const out = execSync('docker exec -i hub-test-api python hub/manage.py shell', {
    encoding: 'utf-8',
    timeout: 120_000,
    input: script,
  });
  // The shell echoes structlog banners on stdout — find the line that
  // JSON-parses to the provisioned payload (the keyed object), never
  // assume line[0] is the payload.
  const payload = out
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => {
      try {
        const outer = JSON.parse(line) as Record<string, unknown>;
        // The container's logging wraps stdout prints in structlog
        // "message" fields — unwrap both shapes.
        if (typeof outer.message === 'string') {
          return JSON.parse(outer.message) as Record<string, unknown>;
        }
        return outer;
      } catch {
        return null;
      }
    })
    .find((obj) => obj !== null && 'export_id' in obj && 'email' in obj);
  if (!payload) {
    throw new Error(`provisioning produced no payload: ${out}`);
  }
  return {
    exportId: String(payload.export_id),
    email: String(payload.email),
    password: String(payload.password),
  } as Provisioned;
}

test.describe('JOURNEY-DB-013: Export a Dataset to Databricks @critical', () => {
  test.setTimeout(120000);

  test('the trigger dispatches the spine and the credential gate refuses fail-closed', async () => {
    const provisioned = provisionExport();
    const token = await login({
      email: provisioned.email,
      password: provisioned.password,
    });

    const response = await fetchWithRetry(
      `${API_BASE_URL}/scheduled-exports/${provisioned.exportId}/trigger/`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({}),
      }
    );
    expect(response.ok, `trigger failed: ${response.status}`).toBeTruthy();
    const body = (await response.json()) as { error_message?: string };

    // The fail-closed credential gate: no scoped write credential
    // material → the classified refusal BEFORE any pipeline work.
    expect(body.error_message, JSON.stringify(body)).toBeTruthy();
    expect(body.error_message).toContain('DLT_CREDENTIAL_NOT_RESOLVED');
  });

  test('the trigger boundary answers 401 without a token', async () => {
    const provisioned = provisionExport();
    const response = await fetchWithRetry(
      `${API_BASE_URL}/scheduled-exports/${provisioned.exportId}/trigger/`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      }
    );
    expect(response.status).toBe(401);
  });
});
