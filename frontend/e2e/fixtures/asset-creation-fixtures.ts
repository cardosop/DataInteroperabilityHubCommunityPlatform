/**
 * E2E fixtures for Phase 250 asset-creation flows.
 *
 * This module provides:
 *
 *   * `seedFailClosedTenant(opts)` — Phase 250.1.B.3 deliverable. Creates
 *     a tenant + DPO user + a file ready to ingest, configured with the
 *     feature flags requested in `opts`. Returns a `FailClosedTenantFixture`
 *     handle exposing the high-level operations the spec needs.
 *
 *   * `expectFailClosedRejection(response)` — assertion helper for the
 *     422 + ASSET_FAIL_CLOSED_REJECTED contract.
 *
 *   * `expectAssetCountEquals(fixture, key, n)` — assertion that exactly
 *     `n` Asset rows exist for the tenant with the given key.
 *
 *   * `expectAuditEventEmitted(fixture, criteria)` — assertion that an
 *     audit event was written matching the criteria.
 *
 * Real backend only; no mocks. The compliance + DQ microservices are
 * exercised live (the seeding helper ensures the test tenant's policy
 * combined with the synthetic file content produces the desired gate
 * outcome).
 *
 * Convention: every helper accepts the Playwright `cleanup` fixture from
 * `test-data-cleanup.ts` so tenants / users / files / audit events are
 * torn down deterministically at test exit.
 */

import { request, type APIRequestContext } from '@playwright/test';
import { expect } from '@playwright/test';
import type { TestUser } from '../setup/create-test-user';
import type { CleanupRegistry } from './test-data-cleanup';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE_URL =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

// ----------------------------------------------------------------------------
// Public types
// ----------------------------------------------------------------------------

export interface SeedFailClosedTenantOpts {
  cleanup: CleanupRegistry;
  /**
   * Sets the tenant's data-storage policy. When `false`, the synthetic
   * compliance scan returns `allowed_to_store=false` and FAIL — the
   * Phase 250.1.A workflow rejects with 422.
   */
  tenantPolicyAllowsStorage: boolean;
  /**
   * Per-tenant kill-switch per D250.12. When `false`, the workflow
   * falls back to legacy create-then-validate (DRAFT persists).
   */
  complianceFailClosedEnabled: boolean;
  /**
   * Optional override for `Tenant.allow_intake_on_compliance_degraded`
   * per D250.9. Default: false.
   */
  allowIntakeOnComplianceDegraded?: boolean;
}

export interface DataFirstAttemptOpts {
  key: string;
  name: string;
  /** Inline file content used when `fileId` is omitted. */
  fileContent?: string;
  /**
   * Use a pre-uploaded file id instead of inline content. When set,
   * `fileContent` is ignored. Used for cross-tenant tests.
   */
  fileId?: string;
}

export interface DataFirstResponse {
  status: number;
  body: Record<string, unknown> & {
    code?: string;
    workflow_run_id?: string;
  };
  headers: Record<string, string>;
}

export interface FailClosedTenantFixture {
  tenantId: string;
  dpoUser: TestUser;
  apiContext: APIRequestContext;

  /**
   * Posts to `/api/v1/assets/data-first/`. If `fileContent` is given,
   * uploads it via the file-upload endpoint first. If `fileId` is given,
   * posts the existing id (for cross-tenant tests).
   */
  attemptDataFirstAssetCreation(
    opts: DataFirstAttemptOpts,
  ): Promise<DataFirstResponse>;

  /** Uploads a file owned by this tenant; returns the resulting file row. */
  uploadFile(opts: { content: string; name: string }): Promise<{ id: string }>;

  /** Fetches the asset by `key`. Throws if not found. */
  fetchAsset(key: string): Promise<{
    id: string;
    status: string;
    compliance_status: string;
    [k: string]: unknown;
  }>;

  /** Polls `/api/v1/workflows/runs/{id}/` until terminal state. */
  pollWorkflowRunUntilTerminal(
    runId: string,
    opts?: { timeoutMs?: number; intervalMs?: number },
  ): Promise<'COMPLETED' | 'FAILED' | 'ABORTED'>;

  /**
   * Tear down resources whose types are NOT in the framework cleanup
   * registry's union (`tenant`, `file`, `audit_event` etc.). Called by
   * the spec in `test.afterEach` for deterministic teardown.
   *
   * The framework's `cleanup.track()` registry handles `asset` /
   * `dataset` / `contract` / `listing` / `order` / `user` resources
   * (per `CleanupResourceType` union in `test-data-cleanup.ts`). This
   * fixture creates resources outside that union (the per-test isolated
   * tenant + the file_id for the upload) and tracks them locally.
   */
  cleanupOrphans(): Promise<void>;
}

// ----------------------------------------------------------------------------
// seedFailClosedTenant — main fixture entry point
// ----------------------------------------------------------------------------

/**
 * Creates an isolated tenant + DPO user + API context wired for fail-
 * closed scenarios. Returns a fixture handle whose methods make the
 * spec read like a UAT script.
 *
 * Implementation notes:
 *
 *   * Creates the tenant via the platform-admin internal API (NOT the
 *     public POST /tenants/ endpoint, which has more restrictive
 *     validation). This requires `E2E_PLATFORM_ADMIN_TOKEN` env var.
 *
 *   * Creates the DPO user via `setup/create-test-user.ts`, scoped to
 *     the new tenant.
 *
 *   * Sets the per-tenant feature flags via the tenant-admin endpoint.
 *
 *   * Registers the tenant + user with the cleanup fixture so the
 *     test_data_cleanup hook tears them down post-test.
 */
export async function seedFailClosedTenant(
  opts: SeedFailClosedTenantOpts,
): Promise<FailClosedTenantFixture> {
  const platformAdminToken = process.env.E2E_PLATFORM_ADMIN_TOKEN;
  if (!platformAdminToken) {
    throw new Error(
      'seedFailClosedTenant requires E2E_PLATFORM_ADMIN_TOKEN to be set; ' +
        'this fixture creates an isolated tenant via the platform-admin API.',
    );
  }

  const apiContext = await request.newContext({ baseURL: API_BASE_URL });
  const tenantSlug = `fail-closed-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;

  // ── Create tenant via platform-admin endpoint ─────────────────────
  const tenantResp = await apiContext.post('/platform/tenants/', {
    headers: { Authorization: `Bearer ${platformAdminToken}` },
    data: {
      name: `Fail-closed test ${tenantSlug}`,
      slug: tenantSlug,
      status: 'ACTIVE',
      kyc_status: 'VERIFIED',
      compliance_fail_closed_enabled: opts.complianceFailClosedEnabled,
      allow_intake_on_compliance_degraded:
        opts.allowIntakeOnComplianceDegraded ?? false,
    },
  });
  if (!tenantResp.ok()) {
    throw new Error(
      `seedFailClosedTenant: failed to create tenant: ${tenantResp.status()} ${await tenantResp.text()}`,
    );
  }
  const tenant = await tenantResp.json();
  // Tenant cleanup is NOT supported by the framework `cleanup.track()`
  // registry (its CleanupResourceType union has 'asset'|'contract'|
  // 'listing'|'dataset'|'order'|'user' — see test-data-cleanup.ts:49).
  // Track the new tenant id locally; the spec's `afterEach` calls
  // `fixture.cleanupOrphans()` to delete it.
  const orphanResources: Array<{ kind: 'tenant' | 'file'; id: string }> = [
    { kind: 'tenant', id: tenant.id },
  ];

  // ── Set the data-storage policy that drives the compliance scan ───
  if (!opts.tenantPolicyAllowsStorage) {
    const policyResp = await apiContext.patch(
      `/platform/tenants/${tenant.id}/compliance-policy/`,
      {
        headers: { Authorization: `Bearer ${platformAdminToken}` },
        data: { allowed_to_store: false },
      },
    );
    if (!policyResp.ok()) {
      throw new Error(
        `seedFailClosedTenant: failed to set compliance policy: ${policyResp.status()}`,
      );
    }
  }

  // ── Create a DPO user scoped to the new tenant via platform-admin API
  //
  // The existing `setup/create-test-user.ts` exports `ensureTestUser`
  // and friends but they all create users against the SHARED per-worker
  // tenant — they cannot create a user on a brand-new isolated tenant.
  // For Phase 250.1.B fail-closed scenarios we need an isolated tenant
  // per test, so we POST directly to the platform-admin user-create
  // endpoint. Falls within the same `E2E_PLATFORM_ADMIN_TOKEN` auth
  // surface used for tenant creation above.
  const userEmail = `dpo-${tenantSlug}@example.com`;
  const userResp = await apiContext.post('/platform/users/', {
    headers: { Authorization: `Bearer ${platformAdminToken}` },
    data: {
      email: userEmail,
      tenant_id: tenant.id,
      password: `${tenantSlug}!Pwd-${Date.now()}`,
      role: 'TENANT_ADMIN',  // DPO maps to TENANT_ADMIN — no separate DPO role.
      status: 'ACTIVE',
    },
  });
  if (!userResp.ok()) {
    throw new Error(
      `seedFailClosedTenant: failed to create DPO user: ${userResp.status()} ${await userResp.text()}`,
    );
  }
  const userData = await userResp.json();
  // Users IS in the cleanup registry's supported types — track via the
  // framework so the user gets deleted at flush.
  // (We synthesise a minimal TestUser shape; access-token comes from
  // the login response below.)
  const loginResp = await apiContext.post('/auth/login/', {
    data: { email: userEmail, password: userData.password ?? '' },
  });
  if (!loginResp.ok()) {
    throw new Error(
      `seedFailClosedTenant: failed to log in DPO user: ${loginResp.status()}`,
    );
  }
  const tokens = await loginResp.json();
  const dpoUser: TestUser = {
    email: userEmail,
    accessToken: tokens.access ?? tokens.access_token ?? '',
    refreshToken: tokens.refresh ?? tokens.refresh_token ?? '',
    userId: userData.id,
    tenantId: tenant.id,
  } as TestUser;
  opts.cleanup.track({ type: 'user', id: userData.id, owner: dpoUser });

  return new FailClosedTenantFixtureImpl(
    apiContext,
    tenant.id,
    dpoUser,
    opts.cleanup,
    orphanResources,
    platformAdminToken,
  );
}

// ----------------------------------------------------------------------------
// Internal implementation
// ----------------------------------------------------------------------------

class FailClosedTenantFixtureImpl implements FailClosedTenantFixture {
  constructor(
    public readonly apiContext: APIRequestContext,
    public readonly tenantId: string,
    public readonly dpoUser: TestUser,
    private readonly cleanup: CleanupRegistry,
    private readonly orphans: Array<{ kind: 'tenant' | 'file'; id: string }>,
    private readonly platformAdminToken: string,
  ) {}

  private get authHeaders(): Record<string, string> {
    return { Authorization: `Bearer ${this.dpoUser.accessToken}` };
  }

  async cleanupOrphans(): Promise<void> {
    // Tear down resources whose types aren't in the framework cleanup
    // registry. Best-effort: 404s are tolerated (already-deleted
    // cascades). Errors are logged but don't fail the test.
    for (const orphan of this.orphans) {
      try {
        if (orphan.kind === 'tenant') {
          await this.apiContext.delete(`/platform/tenants/${orphan.id}/`, {
            headers: { Authorization: `Bearer ${this.platformAdminToken}` },
          });
        } else if (orphan.kind === 'file') {
          await this.apiContext.delete(`/files/${orphan.id}/`, {
            headers: this.authHeaders,
          });
        }
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn(
          `cleanupOrphans: failed to tear down ${orphan.kind}/${orphan.id}: ${String(err)}`,
        );
      }
    }
    this.orphans.length = 0;
  }

  async uploadFile(opts: {
    content: string;
    name: string;
  }): Promise<{ id: string }> {
    // Two-step file upload per existing convention:
    //   1. POST /files/init/ → presigned URL + file_id (PENDING)
    //   2. PUT presigned URL with content
    //   3. POST /files/{id}/complete/ → file ACTIVE
    const initResp = await this.apiContext.post('/files/init/', {
      headers: this.authHeaders,
      data: {
        name: opts.name,
        content_type: 'text/csv',
        size: opts.content.length,
      },
    });
    if (!initResp.ok()) {
      throw new Error(`uploadFile: init failed ${initResp.status()}`);
    }
    const init = await initResp.json();
    // File is NOT a CleanupResourceType in the framework registry —
    // track in the orphan list for fixture-managed teardown.
    this.orphans.push({ kind: 'file', id: init.file_id });

    // Upload to the presigned URL. In E2E with real S3 / MinIO this
    // is a real HTTPS PUT; the test harness expects MinIO at the
    // configured endpoint.
    const uploadResp = await this.apiContext.put(init.upload_url, {
      data: opts.content,
      headers: { 'Content-Type': 'text/csv' },
    });
    if (!uploadResp.ok()) {
      throw new Error(`uploadFile: presigned PUT failed ${uploadResp.status()}`);
    }

    const completeResp = await this.apiContext.post(
      `/files/${init.file_id}/complete/`,
      {
        headers: this.authHeaders,
        data: { sha256: init.expected_sha256 || '' },
      },
    );
    if (!completeResp.ok()) {
      throw new Error(`uploadFile: complete failed ${completeResp.status()}`);
    }

    return { id: init.file_id };
  }

  async attemptDataFirstAssetCreation(
    opts: DataFirstAttemptOpts,
  ): Promise<DataFirstResponse> {
    let fileId = opts.fileId;
    if (!fileId) {
      if (!opts.fileContent) {
        throw new Error(
          'attemptDataFirstAssetCreation: provide either fileId or fileContent',
        );
      }
      const file = await this.uploadFile({
        content: opts.fileContent,
        name: `${opts.key}.csv`,
      });
      fileId = file.id;
    }

    const resp = await this.apiContext.post('/assets/data-first/', {
      headers: this.authHeaders,
      data: {
        file_id: fileId,
        key: opts.key,
        name: opts.name,
      },
    });
    const body = (await resp.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    if (resp.status() === 200 || resp.status() === 201) {
      const assetId = (body as { id?: string }).id;
      if (assetId) {
        // Asset IS a supported CleanupResourceType — use the framework
        // registry (proper teardown order, owner-aware re-login).
        this.cleanup.track({ type: 'asset', id: assetId, owner: this.dpoUser });
      }
    }
    const headers: Record<string, string> = {};
    for (const [k, v] of Object.entries(resp.headers())) {
      headers[k.toLowerCase()] = String(v);
    }
    return { status: resp.status(), body, headers };
  }

  async fetchAsset(key: string): Promise<{
    id: string;
    status: string;
    compliance_status: string;
    [k: string]: unknown;
  }> {
    const resp = await this.apiContext.get(`/assets/?key=${encodeURIComponent(key)}`, {
      headers: this.authHeaders,
    });
    if (!resp.ok()) {
      throw new Error(`fetchAsset: ${resp.status()} ${await resp.text()}`);
    }
    const body = (await resp.json()) as { results?: unknown[] };
    const results = body.results ?? [];
    if (results.length === 0) {
      throw new Error(`fetchAsset: no asset with key=${key}`);
    }
    if (results.length > 1) {
      throw new Error(
        `fetchAsset: ${results.length} assets with key=${key} (expected 0 or 1)`,
      );
    }
    return results[0] as {
      id: string;
      status: string;
      compliance_status: string;
      [k: string]: unknown;
    };
  }

  async pollWorkflowRunUntilTerminal(
    runId: string,
    opts: { timeoutMs?: number; intervalMs?: number } = {},
  ): Promise<'COMPLETED' | 'FAILED' | 'ABORTED'> {
    const timeout = opts.timeoutMs ?? 30_000;
    const interval = opts.intervalMs ?? 500;
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      const resp = await this.apiContext.get(`/workflows/runs/${runId}/`, {
        headers: this.authHeaders,
      });
      if (resp.ok()) {
        const body = (await resp.json()) as { status?: string };
        const status = body.status ?? '';
        if (status === 'COMPLETED' || status === 'FAILED' || status === 'ABORTED') {
          return status;
        }
      }
      await new Promise((r) => setTimeout(r, interval));
    }
    throw new Error(
      `pollWorkflowRunUntilTerminal: timed out after ${timeout}ms; ` +
        'workflow stuck in non-terminal state.',
    );
  }
}

// ----------------------------------------------------------------------------
// Public assertion helpers
// ----------------------------------------------------------------------------

/**
 * Asserts the standard fail-closed contract: HTTP 422 + body code
 * `ASSET_FAIL_CLOSED_REJECTED`. Used by every fail-closed spec.
 */
export function expectFailClosedRejection(response: DataFirstResponse): void {
  expect(
    response.status,
    `expected 422 ASSET_FAIL_CLOSED_REJECTED but got ${response.status}: ${JSON.stringify(response.body)}`,
  ).toBe(422);
  expect(response.body.code).toBe('ASSET_FAIL_CLOSED_REJECTED');
}

/** Asserts exactly `n` Asset rows exist for the tenant with the given key. */
export async function expectAssetCountEquals(
  fixture: FailClosedTenantFixture,
  key: string,
  expectedCount: number,
): Promise<void> {
  const resp = await fixture.apiContext.get(
    `/assets/?key=${encodeURIComponent(key)}`,
    {
      headers: { Authorization: `Bearer ${fixture.dpoUser.accessToken}` },
    },
  );
  if (!resp.ok()) {
    throw new Error(`expectAssetCountEquals: ${resp.status()} ${await resp.text()}`);
  }
  const body = (await resp.json()) as { results?: unknown[] };
  const actual = (body.results ?? []).length;
  expect(actual, `Expected ${expectedCount} asset(s) with key=${key}, got ${actual}`).toBe(
    expectedCount,
  );
}

/**
 * Asserts an audit event was emitted matching the given criteria.
 * `detailsContains` matches against the lowercased JSON-stringified
 * details_json — sufficient for the qualitative checks needed in E2E.
 */
export async function expectAuditEventEmitted(
  fixture: FailClosedTenantFixture,
  criteria: { action: string; detailsContains?: string },
): Promise<void> {
  const resp = await fixture.apiContext.get(
    `/audit/events/?action=${encodeURIComponent(criteria.action)}&tenant_id=${fixture.tenantId}`,
    {
      headers: { Authorization: `Bearer ${fixture.dpoUser.accessToken}` },
    },
  );
  if (!resp.ok()) {
    throw new Error(`expectAuditEventEmitted: ${resp.status()} ${await resp.text()}`);
  }
  const body = (await resp.json()) as { results?: Array<Record<string, unknown>> };
  const events = body.results ?? [];
  expect(
    events.length,
    `Expected at least one audit event with action=${criteria.action}, found ${events.length}`,
  ).toBeGreaterThan(0);

  if (criteria.detailsContains) {
    const needle = criteria.detailsContains.toLowerCase();
    const hay = events
      .map((e) => JSON.stringify(e).toLowerCase())
      .join('\n');
    expect(
      hay.includes(needle),
      `Expected audit-event details to contain ${JSON.stringify(criteria.detailsContains)}, but no match found in ${events.length} event(s).`,
    ).toBe(true);
  }
}
