/**
 * E2E Test: JOURNEY-DB-014 — Ingest from a Databricks Source
 *
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-014.md
 *
 * Real backend, deterministic: two legs. (1) The picker contract (task
 * 6.8): the create form renders the workspace+warehouse picker for
 * DATABRICKS_SOURCE and REFUSES the submit until a warehouse is picked
 * — the derived path is the only stored form, never hand-typed. (2) The
 * fail-closed spine leg: a DATABRICKS_SOURCE ingestion without a
 * warehouse connection fails the REAL trigger with the classified
 * `WAREHOUSE_CONNECTION_REQUIRED` refusal. The tenant + ingestion row
 * are provisioned through the API container's Django shell (the 3.7 CLI
 * real-API pattern); no mocks — the backend decides.
 */

import { expect, test } from '@playwright/test';
import { execSync } from 'node:child_process';
import { getTestUser, gotoWithRetry, loginAsPersona } from '../../fixtures/auth';
import {
  injectTokensBeforeGotoForUser,
  skipIfRemoteApi,
  waitForAppMainReady,
} from '../../fixtures/helpers';

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
  // Same transport retry as the rest of the spec: the login POST rides
  // the same pooled keep-alive as the provisioning-era fetches, so a
  // gunicorn idle close surfaces here too ("other side closed").
  const response = await fetchWithRetry(`${API_BASE_URL}/auth/login/`, {
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
  ingestionId: string;
  email: string;
  password: string;
}

/**
 * A dedicated tenant (data_movement_enabled) + subscription + tenant
 * admin + one DATABRICKS_SOURCE ingestion WITHOUT a warehouse
 * connection — the fail-closed leg is deterministic by construction.
 */
function provisionIngestion(): Provisioned {
  skipIfRemoteApi(test, 'Ingestion provisioning requires docker exec');
  const suffix = Math.random().toString(16).slice(2, 10);
  const script = `
import json
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import Tenant, TenantConfig, TenantPlan
from hub.apps.scheduled_ingestion.models import ScheduledIngestion
from hub.apps.users.models import User, UserStatus

tenant = Tenant.objects.create(
    name='ingest-e2e-${suffix}', slug='ingest-e2e-${suffix}',
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
    email='ingest-e2e-${suffix}@meshant.test',
    password='ingest-pass-${suffix}',
    tenant=tenant,
    status=UserStatus.ACTIVE,
)
ingestion = ScheduledIngestion.objects.create(
    tenant=tenant,
    name='ingest-e2e-${suffix}',
    source_type='DATABRICKS_SOURCE',
    source_config={},
    schedule_type='DAILY',
    schedule_config={'time': '00:00'},
    file_pattern='.*',
    status='ACTIVE',
)
print(json.dumps({
    'ingestion_id': str(ingestion.id),
    'email': user.email,
    'password': 'ingest-pass-${suffix}',
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
    .find((obj) => obj !== null && 'ingestion_id' in obj && 'email' in obj);
  if (!payload) {
    throw new Error(`provisioning produced no payload: ${out}`);
  }
  return {
    ingestionId: String(payload.ingestion_id),
    email: String(payload.email),
    password: String(payload.password),
  } as Provisioned;
}

test.describe('JOURNEY-DB-014: Ingest from a Databricks Source', () => {
  test.setTimeout(120000);

  test('the picker renders for DATABRICKS_SOURCE and the submit is refused without a warehouse', async ({
    page,
  }) => {
    await loginAsPersona(page, getTestUser);
    // The workspace list's fetch rides the session token — re-inject right
    // before the goto (the documented Pattern-B fix: a background refetch
    // can 401 between the login fast-path and the readiness check).
    await injectTokensBeforeGotoForUser(page, await getTestUser());
    await gotoWithRetry(page, '/scheduled-ingestions/create');
    await waitForAppMainReady(page);

    await page.getByLabel(/source type/i).selectOption('DATABRICKS_SOURCE');
    await expect(page.getByLabel(/workspace/i)).toBeVisible();
    await expect(page.getByLabel(/warehouse/i)).toBeVisible();

    await page.getByLabel(/name/i).fill('db-source-journey');
    await page.getByRole('button', { name: /create/i }).click();

    // The fail-closed picker contract: the submit is refused — the
    // derived path is the ONLY stored form, never a placeholder. The
    // `.form-error` target is the submit-refusal alert specifically (the
    // picker renders its own load-error alert under `role="alert"`).
    await expect(page.locator('.form-error').first()).toContainText('derived');
    expect(page.url()).toContain('/scheduled-ingestions/create');
  });

  test('a connectionless DATABRICKS_SOURCE fails the trigger closed', async () => {
    const provisioned = provisionIngestion();
    const token = await login({
      email: provisioned.email,
      password: provisioned.password,
    });

    const response = await fetchWithRetry(
      `${API_BASE_URL}/scheduled-ingestions/${provisioned.ingestionId}/trigger/`,
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
    const body = (await response.json()) as { run_id?: string; run_status?: string };

    // 6.2 dlt dispatch spine (b7 #18): the trigger is ASYNC — it returns
    // run_id immediately with the run PENDING; the RQ worker finalizes
    // COMPLETED/FAILED. The old synchronous contract (error_message +
    // FAILED on the trigger response) was retired with that change, so
    // the refusal must be observed on the RUN ROW, not the trigger body.
    expect(body.run_id, JSON.stringify(body)).toBeTruthy();
    const runId = String(body.run_id);

    // Poll the runs list (serializer field is `status`, unlike the
    // trigger body's `run_status`) until the worker classifies the run.
    await expect
      .poll(
        async () => {
          const runsResp = await fetchWithRetry(
            `${API_BASE_URL}/scheduled-ingestions/${provisioned.ingestionId}/runs/`,
            {
              headers: { Authorization: `Bearer ${token}` },
            }
          );
          const runs = (await runsResp.json()) as Array<{
            id?: string;
            status?: string;
          }>;
          const run = Array.isArray(runs) ? runs.find((r) => r.id === runId) : undefined;
          return run?.status ?? 'PENDING';
        },
        { timeout: 90_000, intervals: [1_000, 2_000, 5_000] }
      )
      .toBe('FAILED');

    // The classified failure: the message names the missing connection key.
    const runsResp = await fetchWithRetry(
      `${API_BASE_URL}/scheduled-ingestions/${provisioned.ingestionId}/runs/`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    const runs = (await runsResp.json()) as Array<{
      id?: string;
      error_message?: string | null;
    }>;
    const run = Array.isArray(runs) ? runs.find((r) => r.id === runId) : undefined;
    expect(run?.error_message, JSON.stringify(run)).toBeTruthy();
    expect(run?.error_message).toContain('warehouse_connection_id');
  });
});
