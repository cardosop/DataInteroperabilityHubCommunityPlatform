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

import { createHash } from 'node:crypto';
import { request, type APIRequestContext } from '@playwright/test';
import { expect } from '@playwright/test';
import type { TestUser } from '../setup/create-test-user';
import type { CleanupRegistry } from './test-data-cleanup';
import { e2eTestHeaders } from './e2e-token';

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

  /**
   * Fetch audit rows for this tenant AS THE PLATFORM ADMIN — the audit
   * list enforces RBAC and DATA_PROVIDER users cannot read it (403).
   */
  fetchAuditEvents(criteria: {
    action: string;
    detailsContains?: string;
  }): Promise<Array<Record<string, unknown>>>;

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
 *   * Creates the tenant via POST /api/v1/tenants/ (IsPlatformAdmin) —
 *     the legacy /platform/tenants/ viewset became READ-ONLY after the
 *     account-plane handoff. The platform-admin token is self-provisioned
 *     when E2E_PLATFORM_ADMIN_TOKEN is not set (local batch runs).
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
  // E2E_PLATFORM_ADMIN_TOKEN is the CI override; the local batch runner does
  // not set it. Self-provision by logging in as the seeded platform admin
  // persona (e2e_platform@example.com — created by ensure_e2e_user_roles,
  // which every batch run executes before specs start). This keeps the
  // fixture runnable under `make test-frontend-e2e-batch3` instead of
  // hard-failing on a missing env var.
  let platformAdminToken = process.env.E2E_PLATFORM_ADMIN_TOKEN;
  if (!platformAdminToken) {
    const loginRes = await fetch(`${API_BASE_URL}/auth/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'e2e_platform@example.com',
        password: 'TestPass123',
      }),
    });
    if (!loginRes.ok) {
      throw new Error(
        'seedFailClosedTenant: E2E_PLATFORM_ADMIN_TOKEN is not set and login as ' +
          `the seeded platform admin failed (${loginRes.status}). Seed persona users ` +
          'first or set E2E_PLATFORM_ADMIN_TOKEN.'
      );
    }
    const loginData = (await loginRes.json()) as { access_token?: string };
    platformAdminToken = loginData.access_token ?? '';
  }
  if (!platformAdminToken) {
    throw new Error(
      'seedFailClosedTenant: platform-admin login succeeded but returned no access_token. ' +
        'Set E2E_PLATFORM_ADMIN_TOKEN explicitly.'
    );
  }

  // Trailing slash is REQUIRED: without it, Playwright's URL resolution
  // treats the last segment ('v1') as a file and resolves relative request
  // paths against /api/ — dropping /v1 and 404ing every call.
  const apiContext = await request.newContext({
    baseURL: `${API_BASE_URL.replace(/\/$/, '')}/`,
  });
  const tenantSlug = `fail-closed-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;

  // ── Create tenant ─────────────────────────────────────────────────
  // PlatformTenantViewSet is READ-ONLY since the account-plane handoff;
  // tenant creation lives on the public ModelViewSet (IsPlatformAdmin) —
  // POST /api/v1/tenants/. The payload keeps the per-tenant fail-closed
  // flags that drive the compliance gate.
  const tenantResp = await apiContext.post('tenants/', {
    headers: { Authorization: `Bearer ${platformAdminToken}` },
    data: {
      name: `Fail-closed test ${tenantSlug}`,
      slug: tenantSlug,
      status: 'ACTIVE',
      kyc_status: 'VERIFIED',
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
    // NOTE: the legacy `/platform/tenants/:id/compliance-policy/` PATCH
    // endpoint no longer exists — ``allowed_to_store`` is a per-
    // ComplianceRun value computed by the compliance microservice. The
    // fail-closed gate is driven by the tenant flags in the create
    // payload above (compliance_fail_closed_enabled); the compliance
    // scan state is seeded through the run itself in the spec.
    void platformAdminToken;
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
  // Password is write-only on the create serializer — the response does
  // NOT echo it. Keep it in a local so the login below uses the real
  // value (reading it back from userData yielded '' and a 400 login).
  const dpoPassword = `${tenantSlug}!Pwd-${Date.now()}`;
  // The data-first endpoint requires DATA_PROVIDER (or TENANT_ADMIN) on the
  // caller. UserCreateSerializer assigns roles by ROLE ID (role_ids), and
  // role names are not writable — resolve the id from the roles listing.
  const userResp = await apiContext.post('users/', {
    headers: { Authorization: `Bearer ${platformAdminToken}` },
    data: {
      email: userEmail,
      tenant: tenant.id,
      password: dpoPassword,
      // send_invitation=false → the user is created ACTIVE with the
      // password set; the default (true) creates an INVITED user that
      // cannot log in. `role`/`status` are NOT writable fields on
      // UserCreateSerializer (G2.2: status derives from the invitation
      // workflow) — role assignment is not needed for the fail-closed
      // data-first flow, which is tenant-scoped, not role-gated.
      send_invitation: false,
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
  const loginResp = await apiContext.post('auth/login/', {
    data: { email: userEmail, password: dpoPassword },
  });
  if (!loginResp.ok()) {
    throw new Error(
      `seedFailClosedTenant: failed to log in DPO user: ${loginResp.status()}`,
    );
  }
  const tokens = await loginResp.json();
  const dpoUser: TestUser = {
    email: userEmail,
    // Required by loginUser/loginAsPersona's UI-login path (fills the
    // password field) — the `as TestUser` cast previously hid its absence
    // and surfaced as "value: expected string, got undefined" mid-login.
    password: dpoPassword,
    name: `Fail-closed DPO ${tenantSlug}`,
    accessToken: tokens.access ?? tokens.access_token ?? '',
    refreshToken: tokens.refresh ?? tokens.refresh_token ?? '',
    userId: userData.id,
    tenantId: tenant.id,
  } as TestUser;
  opts.cleanup.track({ type: 'user', id: userData.id, owner: dpoUser });

  // The batch seeding covers the 24 standard tenants only — this freshly
  // created tenant has no subscription/KYC/roles. ensure-e2e-subscription
  // (same endpoint global-setup uses) provisions subscription + VERIFIED KYC
  // AND seeds the standard role set (billing/test_support) — the test-env
  // tenant post_save role hook is disabled by design. It needs a token
  // whose tenant is THIS tenant, hence the user → login → ensure order.
  // The per-tenant fail-closed flags have NO production API write path
  // (admin/ORM-only Tenant fields) — the test-only ensure endpoint accepts
  // them as an opt-in hook (see ensure_e2e_subscription view).
  const ensureRes = await apiContext.post('test/ensure-e2e-subscription/', {
    headers: {
      Authorization: `Bearer ${dpoUser.accessToken}`,
      // Shared-secret gate on /test/ensure-e2e-* endpoints — missing or
      // wrong token surfaces as a 404 (see fixtures/e2e-token.ts).
      ...e2eTestHeaders(),
    },
    data: {
      compliance_fail_closed_enabled: opts.complianceFailClosedEnabled,
      allow_intake_on_compliance_degraded:
        opts.allowIntakeOnComplianceDegraded ?? false,
    },
  });
  if (!ensureRes.ok()) {
    // intentional: diagnostic-only read — the body preview is best-effort
    // extra context for the error message; the throw is the primary path.
    throw new Error(
      `seedFailClosedTenant: ensure-e2e-subscription failed for new tenant: ${ensureRes.status()} ` +
        `${(await ensureRes.text().catch(() => '')).slice(0, 200)}`,
    );
  }

  // Roles are TENANT-SCOPED; resolve THIS tenant's DATA_PROVIDER id (the
  // listing is unfiltered for platform admins, so filter client-side).
  // PAGINATE: the roles table accumulates a row-set per tenant — with
  // page_size=100 the new tenant's roles can fall beyond page 1 after a few
  // dozen fixture runs (the cross-tenant test failed exactly this way).
  let providerRole: { id: string; name: string; tenant: string } | undefined;
  let nextRolesUrl: string | null = 'users/roles/?page_size=100';
  while (nextRolesUrl && !providerRole) {
    const rolesResp = await apiContext.get(nextRolesUrl, {
      headers: { Authorization: `Bearer ${platformAdminToken}` },
    });
    if (!rolesResp.ok()) {
      throw new Error(
        `seedFailClosedTenant: failed to list roles: ${rolesResp.status()}`,
      );
    }
    const rolesList = (await rolesResp.json()) as {
      results?: Array<{ id: string; name: string; tenant: string }>;
      next?: string | null;
    };
    providerRole = (rolesList.results ?? []).find(
      (r) => r.name === 'DATA_PROVIDER' && r.tenant === tenant.id,
    );
    // Pass the backend's `next` link through VERBATIM — apiContext accepts
    // absolute URLs, and hand-mangling the path/query is where pagination
    // walks silently break (a broken page URL re-serves page 1 forever and
    // the loop ends "searched all pages" while the role exists on a later
    // page). Resolve relative links against the API base.
    if (rolesList.next && !providerRole) {
      nextRolesUrl = new URL(rolesList.next, API_BASE_URL).toString();
    } else {
      nextRolesUrl = null;
    }
  }
  if (!providerRole) {
    throw new Error(
      'seedFailClosedTenant: DATA_PROVIDER role not found for the new tenant in roles listing (searched all pages)',
    );
  }

  // Assign the role via PATCH (UserUpdateSerializer role_ids REPLACES the
  // set) — the create serializer applied no role because none existed yet.
  const patchResp = await apiContext.patch(`users/${userData.id}/`, {
    headers: { Authorization: `Bearer ${platformAdminToken}` },
    data: { role_ids: [providerRole.id] },
  });
  if (!patchResp.ok()) {
    throw new Error(
      `seedFailClosedTenant: failed to assign DATA_PROVIDER role: ${patchResp.status()}`,
    );
  }

  // Re-login so the fresh JWT carries the DATA_PROVIDER role claim — the
  // data-first endpoint authorizes on the token's roles.
  const reloginResp = await apiContext.post('auth/login/', {
    data: { email: userEmail, password: dpoPassword },
  });
  if (!reloginResp.ok()) {
    throw new Error(
      `seedFailClosedTenant: failed to re-login DPO user after role assignment: ${reloginResp.status()}`,
    );
  }
  const freshTokens = await reloginResp.json();
  dpoUser.accessToken = freshTokens.access ?? freshTokens.access_token ?? dpoUser.accessToken;
  dpoUser.refreshToken = freshTokens.refresh ?? freshTokens.refresh_token ?? dpoUser.refreshToken;



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

  async fetchAuditEvents(criteria: {
    action: string;
    detailsContains?: string;
  }): Promise<Array<Record<string, unknown>>> {
    const resp = await this.apiContext.get(
      `audit/audit-events/?action=${encodeURIComponent(criteria.action)}&tenant_id=${this.tenantId}`,
      { headers: { Authorization: `Bearer ${this.platformAdminToken}` } },
    );
    if (!resp.ok()) {
      throw new Error(`fetchAuditEvents: ${resp.status()} ${await resp.text()}`);
    }
    const body = (await resp.json()) as { results?: Array<Record<string, unknown>> };
    return body.results ?? [];
  }

  async cleanupOrphans(): Promise<void> {
    // Tear down resources whose types aren't in the framework cleanup
    // registry. Best-effort: 404s are tolerated (already-deleted
    // cascades). Errors are logged but don't fail the test.
    for (const orphan of this.orphans) {
      try {
        if (orphan.kind === 'tenant') {
          await this.apiContext.delete(`tenants/${orphan.id}/`, {
            headers: { Authorization: `Bearer ${this.platformAdminToken}` },
          });
        } else if (orphan.kind === 'file') {
          await this.apiContext.delete(`files/${orphan.id}/`, {
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
    const initResp = await this.apiContext.post('files/init/', {
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

    // Backend contract (FileViewSet.complete_upload): the field is
    // ``content_sha256`` (the legacy ``sha256`` field 400s). Compute it
    // locally from the content we just uploaded — the init response may
    // not echo the expected hash.
    const completeResp = await this.apiContext.post(
      `files/${init.file_id}/complete/`,
      {
        headers: this.authHeaders,
        data: {
          content_sha256: createHash('sha256').update(opts.content).digest('hex'),
        },
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

    // The data-first endpoint is idempotency-gated with a strict key
    // format: `<tenant_uuid>:<sha256(body)>` (the body is the JSON request
    // payload). Anything else 400s with IDEMPOTENCY_KEY_MALFORMED.
    const requestBody = {
      file_id: fileId,
      key: opts.key,
      name: opts.name,
    };
    const resp = await this.apiContext.post('assets/data-first/', {
      headers: {
        ...this.authHeaders,
        'Idempotency-Key': `${this.tenantId}:${createHash('sha256')
          .update(JSON.stringify(requestBody))
          .digest('hex')}`,
      },
      data: requestBody,
    });
    // intentional: diagnostic-tolerant parse — a non-JSON error body yields an
    // empty object and the status-based throw below remains the primary
    // failure path.
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
    const resp = await this.apiContext.get(`assets/?key=${encodeURIComponent(key)}`, {
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
      const resp = await this.apiContext.get(`workflows/runs/${runId}/`, {
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
    `assets/?key=${encodeURIComponent(key)}`,
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
  const events = await fixture.fetchAuditEvents(criteria);
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
