/**
 * Phase 226 E6 — Disposable-tenant fixture.
 *
 * Provides per-test, fresh, isolated tenants (and users inside each
 * tenant) for cross-tenant negative-assertion specs. Two tenants are
 * provisioned per test (`tenantA`, `tenantB`) plus one user inside each
 * (`userInA`, `userInB`). After the test body completes (success or
 * failure), the fixture cascade-deletes both tenants — which removes
 * every nested asset / dataset / contract / user / etc. — and falls
 * back to the staging-side prefix-purge cron (226.E2) for any row the
 * cascade missed.
 *
 * Architectural decision (D124 — design.md): on-the-fly provisioning,
 * NOT pool-based. Cost is ~5–10s per spec that needs disposable
 * tenants, but every spec gets a tenant whose first write is the first
 * in its DB history — no cross-test contamination from a pool's wipe-
 * before-return bug. Migrate to pool-based only when CI wall-time hurts
 * (currently <15 specs are expected to need disposable tenants).
 *
 * Backend prerequisite (226.OQ4): `POST /api/v1/tenants/ephemeral/`
 * must exist on the target backend. The endpoint accepts:
 *
 *     { name?: string, label?: string }   (both optional; server-defaulted)
 *
 * and returns:
 *
 *     {
 *       id: string,           // tenant id (UUID)
 *       name: string,
 *       admin_user: {
 *         id: string,
 *         email: string,
 *         password: string,   // ONLY returned by the ephemeral endpoint
 *       }
 *     }
 *
 * Cascade delete is `DELETE /api/v1/tenants/{id}/?cascade=true`. If the
 * endpoint is missing, the fixture throws on first use with a clear
 * pointer to OQ4 — the failure mode is loud, not silent.
 *
 * Wiring: import `disposableTenantTest` (instead of `guardedTest`) from
 * this module. The new fixture EXTENDS guardedTest, so all the existing
 * guards (page-error, console-error, 5xx, correlation-id, createdResources)
 * still fire on every spec.
 *
 * No mocks. Real backend only.
 */

import {
  test as guardedTest,
  expect,
} from './guardedTest';
import type { TestUser } from '../setup/create-test-user';
import { randomBytes } from 'node:crypto';

// ---------------------------------------------------- types

export interface DisposableTenant {
  id: string;
  name: string;
  /** The admin user automatically provisioned by the ephemeral endpoint. */
  admin: TestUser & { id: string };
}

export interface DisposableTenantFixture {
  tenantA: DisposableTenant;
  tenantB: DisposableTenant;
  /** Convenience aliases — `userInA === tenantA.admin`. Spec authors find
   * the user-side names more readable in cross-tenant assertions. */
  userInA: TestUser & { id: string };
  userInB: TestUser & { id: string };
}

// ---------------------------------------------------- pure logic (testable)

/** API base URL resolution — mirrors createdResources.ts so a single
 * source-of-truth governs both fixture endpoints. */
export function resolveApiBase(env: Record<string, string | undefined> = process.env): string {
  const defaultPort = env.E2E_WEB_PORT ? '8001' : '8000';
  if (env.E2E_API_BASE_URL) return env.E2E_API_BASE_URL;
  if (env.VITE_PROXY_TARGET) return `${env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`;
  if (env.VITE_API_BASE_URL && env.VITE_API_BASE_URL.startsWith('http')) {
    return env.VITE_API_BASE_URL;
  }
  return `http://localhost:${defaultPort}/api/v1`;
}

/** Build the ephemeral-tenant POST URL. Pure for testability. */
export function ephemeralTenantUrl(apiBase: string): string {
  return `${apiBase.replace(/\/$/, '')}/tenants/ephemeral/`;
}

/** Build the cascade-delete URL for a tenant id. Pure. */
export function cascadeDeleteTenantUrl(apiBase: string, tenantId: string): string {
  return `${apiBase.replace(/\/$/, '')}/tenants/${tenantId}/?cascade=true`;
}

/** Generate a unique, traceable tenant name embedding the run-id and a
 * disambiguator (A/B). The `e2e-` prefix means the staging-side
 * prefix-purge cron will sweep any leak even if cascade-delete fails.
 *
 * Pure: takes a clock + random source so the test can pin output. */
export function buildTenantName(opts: {
  runId: string;
  slot: 'A' | 'B';
  rand?: () => string;
  now?: () => number;
}): string {
  const rand = opts.rand ?? (() => randomBytes(4).toString('hex'));
  const now = opts.now ?? (() => Date.now());
  return `e2e-tenant-${opts.slot}-${opts.runId.slice(0, 8)}-${now()}-${rand()}`;
}

/** Validate the shape of the ephemeral-tenant POST response. The fixture
 * trusts the backend on field types but rejects missing keys early so a
 * silent rename surfaces immediately rather than as a downstream TypeError. */
export function parseEphemeralTenantResponse(payload: unknown): DisposableTenant {
  if (!payload || typeof payload !== 'object') {
    throw new Error('ephemeral-tenant response: not an object');
  }
  const p = payload as Record<string, unknown>;
  const id = p.id;
  const name = p.name;
  const admin = p.admin_user as Record<string, unknown> | undefined;
  if (typeof id !== 'string' || !id) {
    throw new Error('ephemeral-tenant response: missing or non-string `id`');
  }
  if (typeof name !== 'string' || !name) {
    throw new Error('ephemeral-tenant response: missing or non-string `name`');
  }
  if (!admin || typeof admin !== 'object') {
    throw new Error('ephemeral-tenant response: missing `admin_user`');
  }
  const adminId = admin.id;
  const adminEmail = admin.email;
  const adminPassword = admin.password;
  if (typeof adminId !== 'string' || typeof adminEmail !== 'string' || typeof adminPassword !== 'string') {
    throw new Error('ephemeral-tenant response: admin_user missing id/email/password');
  }
  return {
    id,
    name,
    admin: {
      id: adminId,
      email: adminEmail,
      password: adminPassword,
      name: adminEmail.split('@')[0] ?? adminEmail,
    },
  };
}

// ---------------------------------------------------- HTTP helpers

interface TenantHttpDeps {
  fetchImpl?: typeof fetch;
  env?: Record<string, string | undefined>;
}

/** Provision one ephemeral tenant via `POST /tenants/ephemeral/`. Throws
 * on non-2xx with a message that points at OQ4 so the failure mode is
 * actionable, not "TypeError: cannot read property id". */
export async function provisionTenant(
  slot: 'A' | 'B',
  runId: string,
  deps: TenantHttpDeps = {},
): Promise<DisposableTenant> {
  const env = deps.env ?? process.env;
  const fetchImpl = deps.fetchImpl ?? fetch;
  const apiBase = resolveApiBase(env);
  const url = ephemeralTenantUrl(apiBase);
  const name = buildTenantName({ runId, slot });
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  // Honour the e2e-token shared header used by other test endpoints —
  // ephemeral-tenant should be gated by the same shared secret.
  if (env.E2E_TEST_TOKEN) headers['x-e2e-token'] = env.E2E_TEST_TOKEN;
  const res = await fetchImpl(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({ name, label: `e2e-${slot}` }),
  });
  if (res.status === 404) {
    throw new Error(
      `disposableTenant: POST ${url} returned 404 — the ephemeral-tenant ` +
      `endpoint is not deployed on this backend. See Phase 226 OQ4 ` +
      `(stand up POST /api/v1/tenants/ephemeral/ on staging) before using ` +
      `disposableTenantTest. Until then, specs that need cross-tenant ` +
      `isolation must continue to use the static test tenants.`,
    );
  }
  if (!res.ok) {
    // intentional: best-effort body read for diagnostic context only;
    // the throw below is the primary failure path.
    const body = await res.text().catch(() => '');
    throw new Error(
      `disposableTenant: POST ${url} → ${res.status} ${body.slice(0, 300)}`,
    );
  }
  // intentional: best-effort json parse; bad payload is rejected by parseEphemeralTenantResponse.
  const payload = await res.json().catch(() => null);
  return parseEphemeralTenantResponse(payload);
}

/** Cascade-delete a tenant. 404 is treated as success (already gone).
 * Returns the (best-effort) string outcome; never throws — the fixture
 * teardown logs failures into a `cleanup-failed` annotation rather than
 * masking the original test failure. */
export async function cascadeDeleteTenant(
  tenantId: string,
  adminToken: string,
  deps: TenantHttpDeps = {},
): Promise<{ ok: boolean; reason?: string }> {
  const env = deps.env ?? process.env;
  const fetchImpl = deps.fetchImpl ?? fetch;
  const url = cascadeDeleteTenantUrl(resolveApiBase(env), tenantId);
  try {
    const res = await fetchImpl(url, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`,
      },
    });
    if (res.ok || res.status === 404) return { ok: true };
    // intentional: best-effort body read for the failure annotation only.
    const body = await res.text().catch(() => '');
    return { ok: false, reason: `${res.status} ${body.slice(0, 200)}` };
  } catch (err) {
    return { ok: false, reason: `threw: ${(err as Error).message}` };
  }
}

// ---------------------------------------------------- Playwright fixture

import { loginViaApi } from './auth';
import { E2E_RUN_ID } from './createdResources';

export const disposableTenantTest = guardedTest.extend<DisposableTenantFixture>({
  tenantA: async ({}, use, testInfo) => {
    const t = await provisionTenant('A', E2E_RUN_ID);
    await use(t);
    // Teardown — re-login as admin to get a fresh token (long tests can
    // outlive token TTL), then cascade-delete.
    let token: string | null = null;
    try {
      token = (await loginViaApi(t.admin.email, t.admin.password)).access_token;
    } catch (err) {
      testInfo.annotations.push({
        type: 'cleanup-failed',
        description: `disposableTenant.tenantA teardown re-login failed: ${(err as Error).message}`,
      });
      return;
    }
    const result = await cascadeDeleteTenant(t.id, token);
    if (!result.ok) {
      testInfo.annotations.push({
        type: 'cleanup-failed',
        description: `disposableTenant.tenantA cascade-delete failed: ${result.reason}`,
      });
    }
  },
  tenantB: async ({}, use, testInfo) => {
    const t = await provisionTenant('B', E2E_RUN_ID);
    await use(t);
    let token: string | null = null;
    try {
      token = (await loginViaApi(t.admin.email, t.admin.password)).access_token;
    } catch (err) {
      testInfo.annotations.push({
        type: 'cleanup-failed',
        description: `disposableTenant.tenantB teardown re-login failed: ${(err as Error).message}`,
      });
      return;
    }
    const result = await cascadeDeleteTenant(t.id, token);
    if (!result.ok) {
      testInfo.annotations.push({
        type: 'cleanup-failed',
        description: `disposableTenant.tenantB cascade-delete failed: ${result.reason}`,
      });
    }
  },
  userInA: async ({ tenantA }, use) => {
    await use(tenantA.admin);
  },
  userInB: async ({ tenantB }, use) => {
    await use(tenantB.admin);
  },
});

export { expect };
