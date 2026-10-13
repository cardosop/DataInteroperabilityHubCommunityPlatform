/**
 * Shared helpers for the DE scheduled-ingestion/export journeys
 * (JOURNEY-INGESTION-001/003, JOURNEY-EXPORT-001).
 *
 * The journeys provision a dedicated tenant (data_movement_enabled=True —
 * the dlt dispatch spine) with a free-plan ACTIVE subscription and one
 * user through the API container's Django shell (the 3.7 CLI real-API
 * pattern, same as JOURNEY-DB-014.spec.ts). No mocks — the backend
 * decides.
 */
import { execSync } from 'node:child_process';
import { expect } from '@playwright/test';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
export const API_BASE_URL =
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
 * The retry opens a fresh connection.
 */
export async function fetchWithRetry(url: string, init?: RequestInit): Promise<Response> {
  try {
    return await globalThis.fetch(url, init);
  } catch (error) {
    if (!(error instanceof TypeError) || !/fetch failed/.test(error.message)) {
      throw error;
    }
    return globalThis.fetch(url, init);
  }
}

export async function login(user: { email: string; password: string }): Promise<string> {
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

export interface ProvisionedTenant {
  email: string;
  password: string;
}

/**
 * A dedicated tenant (data_movement_enabled=True) + TenantConfig +
 * free-plan ACTIVE subscription + one ACTIVE user. The journeys create
 * their ingestion/export rows through the UI — nothing is pre-created.
 */
export function provisionTenant(): ProvisionedTenant {
  const suffix = Math.random().toString(16).slice(2, 10);
  const script = `
import json
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import Tenant, TenantConfig, TenantPlan
from django.utils import timezone
from hub.apps.users.models import Role, User, UserRole, UserStatus
from hub.apps.users.services import UserTenantMembershipService

tenant = Tenant.objects.create(
    name='sched-e2e-${suffix}', slug='sched-e2e-${suffix}',
    data_movement_enabled=True,
)
# The asset-creation gate (Phase 250.6.D.3) blocks with
# ONBOARDING_INCOMPLETE while onboarding_completed_at IS NULL.
tenant.onboarding_completed_at = timezone.now()
tenant.save(update_fields=['onboarding_completed_at'])
TenantConfig.objects.get_or_create(tenant=tenant)
free_plan = TenantPlan.objects.filter(slug='free', is_active=True).first()
if free_plan:
    Subscription.objects.get_or_create(
        tenant=tenant,
        plan=free_plan,
        defaults={'status': SubscriptionStatus.ACTIVE},
    )
user = User.objects.create_user(
    email='sched-e2e-${suffix}@meshant.test',
    password='sched-pass-${suffix}',
    tenant=tenant,
    status=UserStatus.ACTIVE,
)
UserTenantMembershipService().add_membership(user, tenant)
# The scheduled-ingestion/export UI routes are ProtectedRoute-gated on
# DATA_PROVIDER (routes.tsx) — a roleless user lands on 403.
provider_role, _ = Role.objects.get_or_create(
    tenant=tenant, name='DATA_PROVIDER',
    defaults={'description': 'Data Provider'},
)
UserRole.objects.get_or_create(user=user, tenant=tenant, role=provider_role)
print(json.dumps({
    'email': user.email,
    'password': 'sched-pass-${suffix}',
}))
`;
  const payload = parseDockerExecJson(script, ['email', 'password']);
  return {
    email: String(payload.email),
    password: String(payload.password),
  };
}

/**
 * Run a Django-shell script inside the API container and parse the
 * JSON payload line (structlog banners are tolerated — the keyed
 * object is found by its required keys, never by line position).
 */
export function parseDockerExecJson(
  script: string,
  requiredKeys: string[]
): Record<string, unknown> {
  const out = execSync('docker exec -i hub-test-api python hub/manage.py shell', {
    encoding: 'utf-8',
    timeout: 120_000,
    input: script,
  });
  const payload = out
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => {
      try {
        const outer = JSON.parse(line) as Record<string, unknown>;
        if (typeof outer.message === 'string') {
          return JSON.parse(outer.message) as Record<string, unknown>;
        }
        return outer;
      } catch {
        return null;
      }
    })
    .find((obj) => obj !== null && requiredKeys.every((k) => k in obj));
  if (!payload) {
    throw new Error(`provisioning produced no payload: ${out}`);
  }
  return payload;
}
