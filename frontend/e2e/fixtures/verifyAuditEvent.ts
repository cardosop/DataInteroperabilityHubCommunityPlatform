/**
 * `verifyAuditEvent` — dual-channel helper for the audit-trail guarantee.
 *
 * Meshant has ~104 `create_audit_event` call sites across `hub/apps/*`.
 * Every mutation through the UI is supposed to write an `AuditEvent` row;
 * UI-only tests cannot detect a dropped audit write. This helper asks the
 * backend directly:
 *
 *     GET /api/v1/audit/events/?resource_id=<id>&action=<ACTION>&page_size=5
 *
 * and asserts the expected row is present, with a configurable
 * retry-with-backoff budget to tolerate async audit-writer lag.
 *
 * Shape mirrors `verifyViaApi` for reader familiarity:
 *     await verifyAuditEvent(page, {
 *       action: 'ASSET_CREATED',
 *       resourceType: 'ASSET',
 *       resourceId: assetId,
 *     });
 *
 * Pure-logic split out so `_guards.spec.ts` can unit-test every branch
 * without a browser or network:
 *   - `findMatchingAuditEvent(rows, expectation)` — matcher only.
 *   - `pollForAuditEvent(fetcher, expectation + budget)` — retry loop with
 *     an injected fetcher, so tests can feed it canned responses without
 *     pretending to be the backend.
 *
 * The browser-facing `verifyAuditEvent(page, ...)` wires page.request.get
 * into `pollForAuditEvent` and carries the Bearer-token extraction.
 *
 * Phase 226 PR B3 — see
 * /home/ph/.claude/plans/now-pls-create-a-binary-cloud.md §Track B.
 */

import type { Page } from '@playwright/test';

/** Shape of a row returned by `GET /api/v1/audit/audit-events/`. Matches the
 * backend `AuditEventSerializer` at `hub/apps/audit/serializers.py:8-29`.
 *
 * NB: the serializer field names differ from the DB column names — the
 * response uses `tenant` / `actor_user` (FK id strings) rather than
 * `tenant_id` / `actor_user_id`. The `correlation_id` column does NOT exist
 * on the audit model today; the helper's `correlationId` filter therefore
 * no-ops gracefully (see `findMatchingAuditEvent`). Adding correlation_id
 * is tracked as a Track H item alongside the other B4-ready backend work.
 */
export interface AuditEventRow {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  /** FK id or null (system events). Per `AuditEventSerializer.fields`. */
  actor_user: string | null;
  actor_user_email?: string | null;
  /** FK id (tenant scoping). Per `AuditEventSerializer.fields`. */
  tenant: string | null;
  tenant_name?: string | null;
  result: 'SUCCESS' | 'FAILURE' | string;
  details_json?: Record<string, unknown> | null;
  /** ISO-8601. Per `AuditEventSerializer.fields` — column is `timestamp`
   * (not `created_at`). */
  timestamp: string;
  /** Not currently in the serializer or model; reserved for future wiring
   * so B4's correlation-ID guard can cross-check without a type change. */
  correlation_id?: string | null;
}

export interface AuditEventExpectation {
  /** `action` column — e.g. `ASSET_CREATED`, `CONTRACT_ATTACHED`. Required. */
  action: string;
  /** `resource_type` column — e.g. `ASSET`. Required. */
  resourceType: string;
  /** `resource_id` column — the UUID of the mutated resource. Required. */
  resourceId: string;
  /** Optional filter — matches the actor. */
  actorUserId?: string;
  /** Optional filter — matches the tenant. */
  tenantId?: string;
  /** Optional filter — matches the correlation ID (pairs with B4 guard). */
  correlationId?: string;
}

export interface FindResult {
  matched: AuditEventRow | null;
  /** Human-readable reason the match failed, when `matched === null`.
   * Includes row count + nearest-miss diagnostics so teardown messages
   * are debuggable. */
  mismatch: string | null;
}

/**
 * Pure matcher — given a list of rows and an expectation, return the first
 * matching row (in the order the API returned them) or a mismatch message
 * describing why nothing matched.
 *
 * Returns the row rather than a boolean so callers can chain further checks
 * (e.g. `verifyAuditEvent` with correlation-ID cross-check).
 */
export function findMatchingAuditEvent(
  rows: readonly AuditEventRow[],
  expected: AuditEventExpectation,
): FindResult {
  if (rows.length === 0) {
    return {
      matched: null,
      mismatch:
        `no matching audit row: 0 rows returned from API for ` +
        `resource_id=${expected.resourceId} action=${expected.action}.`,
    };
  }

  for (const row of rows) {
    if (row.action !== expected.action) continue;
    if (row.resource_type !== expected.resourceType) continue;
    if (row.resource_id !== expected.resourceId) continue;
    if (expected.actorUserId !== undefined && row.actor_user !== expected.actorUserId) continue;
    if (expected.tenantId !== undefined && row.tenant !== expected.tenantId) continue;
    // Correlation-id column does not exist on the audit model today; the
    // filter only fires when the backend starts emitting it. Rows without
    // the field are not rejected by this filter — keeping backward compat.
    if (
      expected.correlationId !== undefined &&
      row.correlation_id !== undefined &&
      row.correlation_id !== null &&
      row.correlation_id !== expected.correlationId
    ) {
      continue;
    }
    return { matched: row, mismatch: null };
  }

  // No row matched — build a diagnostic message that cites the closest row's
  // actual values so a reviewer sees "why not" at a glance.
  const closest = rows[0];
  const diff: string[] = [];
  if (closest.action !== expected.action) {
    diff.push(`action: expected=${expected.action}, actual=${closest.action}`);
  }
  if (closest.resource_type !== expected.resourceType) {
    diff.push(
      `resource_type: expected=${expected.resourceType}, actual=${closest.resource_type}`,
    );
  }
  if (closest.resource_id !== expected.resourceId) {
    diff.push(
      `resource_id: expected=${expected.resourceId}, actual=${closest.resource_id}`,
    );
  }
  if (expected.actorUserId !== undefined && closest.actor_user !== expected.actorUserId) {
    diff.push(
      `actor_user: expected=${expected.actorUserId}, actual=${closest.actor_user}`,
    );
  }
  if (expected.tenantId !== undefined && closest.tenant !== expected.tenantId) {
    diff.push(
      `tenant: expected=${expected.tenantId}, actual=${closest.tenant}`,
    );
  }
  if (
    expected.correlationId !== undefined &&
    closest.correlation_id !== undefined &&
    closest.correlation_id !== null &&
    closest.correlation_id !== expected.correlationId
  ) {
    diff.push(
      `correlation_id: expected=${expected.correlationId}, actual=${closest.correlation_id}`,
    );
  }

  return {
    matched: null,
    mismatch:
      `no matching audit row among ${rows.length} candidate row${rows.length === 1 ? '' : 's'}. ` +
      `Nearest-row diff: ${diff.length > 0 ? diff.join('; ') : '(none — multi-field multi-candidate miss)'}.`,
  };
}

export type AuditEventFetcher = () => Promise<readonly AuditEventRow[]>;

export interface PollOptions {
  /** Total time budget in ms across all attempts. Default 3_000.
   *
   * Audit emission is **synchronous** in `hub/apps/audit/utils.py:239`
   * (direct `AuditEvent.objects.create(...)` in the request thread; zero
   * `.delay()` / `apply_async` callsites — verified for OQ1). The row is
   * already committed by the time the mutation response returns; the only
   * source of lag is replication / read-after-write on the audit list
   * endpoint. 3 s is generous for that — anything longer is masking a
   * different problem (DB contention, parallel-worker pool starvation,
   * RBAC misconfiguration on the verifier identity) that we'd rather see
   * fail than absorb.
   *
   * Specs that knowingly exercise an async-dispatched event (e.g. anything
   * piggy-backed on the email queue or webhook delivery) should set this
   * explicitly to a higher value with a comment citing the dispatch path.
   */
  retryBudgetMs?: number;
  /** Interval between attempts in ms. Default 500. */
  pollIntervalMs?: number;
}

/**
 * Retry loop with injected fetcher — unit-testable without network.
 *
 * Fetches rows, runs the matcher, and retries until either a match appears
 * or the budget exhausts. Total attempt count is roughly
 * `ceil(retryBudgetMs / pollIntervalMs) + 1` (one initial attempt + retries).
 */
export async function pollForAuditEvent(
  fetcher: AuditEventFetcher,
  expected: AuditEventExpectation & PollOptions,
): Promise<AuditEventRow> {
  const retryBudgetMs = expected.retryBudgetMs ?? 3_000;
  const pollIntervalMs = expected.pollIntervalMs ?? 500;
  const deadline = Date.now() + retryBudgetMs;

  let lastMismatch = 'no attempts made (0 ms budget?)';

  // Always take at least one shot, even if budget is near-zero.
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const rows = await fetcher();
    const result = findMatchingAuditEvent(rows, expected);
    if (result.matched) return result.matched;
    lastMismatch = result.mismatch ?? lastMismatch;

    if (Date.now() >= deadline) break;

    const remaining = deadline - Date.now();
    const sleepMs = Math.min(pollIntervalMs, Math.max(0, remaining));
    await new Promise((resolve) => setTimeout(resolve, sleepMs));
    if (Date.now() >= deadline) {
      // one final attempt after the last sleep window
      const finalRows = await fetcher();
      const finalResult = findMatchingAuditEvent(finalRows, expected);
      if (finalResult.matched) return finalResult.matched;
      lastMismatch = finalResult.mismatch ?? lastMismatch;
      break;
    }
  }

  throw new Error(
    `verifyAuditEvent: exhausted ${retryBudgetMs} ms retry budget without finding audit row. ${lastMismatch}`,
  );
}

async function extractBearerHeaders(
  page: Page,
  override?: Record<string, string>,
): Promise<Record<string, string>> {
  if (override !== undefined) return override;
  const token = await page.evaluate<string | null>(
    () =>
      (globalThis as unknown as { localStorage?: { getItem: (k: string) => string | null } })
        .localStorage?.getItem('access_token') ?? null,
  );
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

// Side-channel audit-read token support.
//
// Root-cause: `GET /api/v1/audit/audit-events/` enforces RBAC via
// `HasAnyRole(AUDIT_READ_ROLES)` at `hub/apps/audit/views.py:75` with
// `AUDIT_READ_ROLES = ["TENANT_ADMIN", "AUDITOR", "PLATFORM_ADMIN"]`. Most
// E2E specs authenticate as a `DATA_PROVIDER` (e.g. `e2e_test@example.com`)
// which does NOT have that permission — the backend returns 403. Giving
// every primary test user `AUDITOR` would poison the permission profile
// we're actually supposed to be testing.
//
// Default verifier identity: `e2e_platform@example.com` (seeded by
// `hub/apps/users/management/commands/ensure_e2e_user_roles.py` with
// `is_platform_admin=True`). Why platform admin and not the dedicated
// AUDITOR account?
//
//   1. JOURNEY-AUTH-001 registers a brand-new user via the UI; the new
//      user is placed in their own *personal* tenant, NOT the seeded
//      `default` tenant. AuditEventViewSet.get_queryset filters to the
//      caller's tenant unless they're platform admin (views.py:96-105).
//      An AUDITOR-role account in `default` cannot see the personal-tenant
//      audit row. A platform admin sees all tenants.
//   2. Audit verification is a TEST INFRASTRUCTURE concern — it asks "did
//      the backend write this row?", an inherently cross-tenant question.
//      Production auditors typically have cross-tenant access too.
//   3. `HasAnyRole` bypasses for `is_platform_admin=True`
//      (permissions.py:154), so the empty-roles platform admin still passes
//      the audit-read RBAC gate.
//
// The token is fetched at most once per worker process (lazy + promise-
// cached, so concurrent verifyAuditEvent calls share the single login).
//
// Credential overrides (for non-default environments / staging secrets /
// tenant-isolation tests):
//   E2E_AUDIT_VERIFIER_EMAIL      default `e2e_platform@example.com`
//   E2E_AUDIT_VERIFIER_PASSWORD   default `TestPass123`
//   E2E_AUDIT_VERIFIER_DISABLED   `1`/`true` → skip side-channel entirely
//                                  (falls back to primary token; useful
//                                  when running against a test DB where
//                                  the primary user already has audit read,
//                                  or when a spec explicitly tests the
//                                  AUDITOR role's tenant-scoped view by
//                                  setting E2E_AUDIT_VERIFIER_EMAIL=
//                                  e2e_auditor@example.com).

let auditorTokenPromise: Promise<string | null> | null = null;
let auditorFailureReason: string | null = null;

/** Test-hook: reset the module-level auditor-token cache. Used by unit
 * tests in `_guards.spec.ts` to isolate per-test state; production code
 * should never call this. */
export function __resetAuditorTokenCacheForTests(): void {
  auditorTokenPromise = null;
  auditorFailureReason = null;
}

function isAuditorSideChannelDisabled(): boolean {
  const raw = process.env.E2E_AUDIT_VERIFIER_DISABLED;
  if (!raw) return false;
  return raw === '1' || raw.toLowerCase() === 'true';
}

async function loadAuditorToken(page: Page): Promise<string | null> {
  const email = process.env.E2E_AUDIT_VERIFIER_EMAIL ?? 'e2e_platform@example.com';
  const password = process.env.E2E_AUDIT_VERIFIER_PASSWORD ?? 'TestPass123';

  // Retry on 429 — the auth burst limiter is shared across the worker pool;
  // when multiple specs verify audit at once, the verifier login can trip
  // the limiter (10s window). Without this retry, the cached promise
  // resolves to null on the first 429 and every subsequent verifyAuditEvent
  // in this worker falls back to the primary token (which 403s for
  // non-audit-role users).
  const RETRY_DELAYS_MS = [1000, 3000, 6000, 10000, 15000];
  let res: Awaited<ReturnType<typeof page.request.post>> | null = null;
  try {
    for (let attempt = 0; attempt <= RETRY_DELAYS_MS.length; attempt++) {
      res = await page.request.post('/api/v1/auth/login/', {
        data: { email, password },
        headers: { 'Content-Type': 'application/json' },
      });
      if (res.ok()) break;
      if (res.status() === 429 && attempt < RETRY_DELAYS_MS.length) {
        const retryAfterRaw = res.headers()['retry-after'];
        const retryAfterSec = retryAfterRaw ? parseInt(retryAfterRaw, 10) : NaN;
        const delay = Number.isFinite(retryAfterSec) && retryAfterSec > 0
          ? retryAfterSec * 1000
          : RETRY_DELAYS_MS[attempt];
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }
      break;
    }
    if (!res || !res.ok()) {
      auditorFailureReason =
        `POST /api/v1/auth/login/ for audit verifier '${email}' returned ${res?.status() ?? 'no-response'} after retries. ` +
        `Seed with \`python hub/manage.py ensure_e2e_user_roles\` against the target environment, ` +
        `or override credentials via E2E_AUDIT_VERIFIER_EMAIL / E2E_AUDIT_VERIFIER_PASSWORD.`;
      return null;
    }
    // Token extraction mirrors the canonical pattern at
    // frontend/e2e/setup/create-test-user.ts:447-452. The login response
    // shape: `{ access_token: string, refresh_token: string, user: {...} }`
    // with `access_token` snake-cased (NOT `access` or `token`). Phase 220.4
    // additionally enables HTTP-only cookie auth (USE_HTTPONLY_AUTH_COOKIES)
    // where `access_token` lives in a `Set-Cookie` header rather than the
    // body — both paths are honored so the helper works regardless of the
    // target environment's cookie-mode flag.
    const body = (await res!.json().catch(() => ({}))) as { access_token?: string };
    const setCookieHeaders = res!
      .headersArray()
      .filter((h) => h.name.toLowerCase() === 'set-cookie')
      .map((h) => h.value);
    const setCookie = setCookieHeaders.join(', ');
    const cookieMatch = setCookie.match(/(?:^|,\s*)access_token=([^;,]+)/i);
    const token = body.access_token ?? cookieMatch?.[1] ?? null;
    if (!token) {
      auditorFailureReason =
        `Login for '${email}' returned 200 but neither response.access_token nor a ` +
        `Set-Cookie access_token=... pair was found. ` +
        `Set-Cookie preview: ${setCookie.slice(0, 200) || '(empty)'}.`;
      return null;
    }
    return token;
  } catch (err) {
    auditorFailureReason =
      `Login request for '${email}' threw: ${err instanceof Error ? err.message : String(err)}`;
    return null;
  }
}

function ensureAuditorToken(page: Page): Promise<string | null> {
  if (isAuditorSideChannelDisabled()) return Promise.resolve(null);
  if (auditorTokenPromise === null) {
    auditorTokenPromise = loadAuditorToken(page);
  }
  return auditorTokenPromise;
}

export interface VerifyAuditEventOptions extends PollOptions {
  /** Override the auth extraction. When set, disables auditor side channel
   * entirely — caller has already chosen the identity to read audit under. */
  authHeaderOverride?: Record<string, string>;
  /** Override the audit list endpoint. Default `/api/v1/audit/events/`. */
  auditEndpoint?: string;
  /** Opt out of the auditor side channel for this call, forcing use of
   * the primary session's token. Useful for tests that specifically
   * assert a non-auditor's visibility into their own audit trail. When
   * unset, the default is to use the auditor token if available. */
  disableAuditorSideChannel?: boolean;
}

/**
 * Browser-facing helper. Composes Bearer-header extraction + fetcher +
 * pollForAuditEvent into a single one-liner for specs.
 *
 * Returns the matched row so callers can do additional assertions (e.g.
 * extract `correlation_id` for cross-channel checks in Phase 226 G9).
 */
export async function verifyAuditEvent(
  page: Page,
  expected: AuditEventExpectation,
  options: VerifyAuditEventOptions = {},
): Promise<AuditEventRow> {
  // Identity resolution order:
  //   1. Explicit authHeaderOverride — caller already chose the identity.
  //   2. Auditor side channel (default; opt-out via disableAuditorSideChannel
  //      or env var E2E_AUDIT_VERIFIER_DISABLED=1).
  //   3. Primary session token — last-resort when auditor account is absent
  //      (e.g. a test env that hasn't run ensure_e2e_user_roles). Will fail
  //      with a clear 403 error on strict environments.
  let headers: Record<string, string>;
  let identityUsed: 'override' | 'auditor' | 'primary';
  if (options.authHeaderOverride !== undefined) {
    headers = options.authHeaderOverride;
    identityUsed = 'override';
  } else if (options.disableAuditorSideChannel) {
    headers = await extractBearerHeaders(page);
    identityUsed = 'primary';
  } else {
    const auditorToken = await ensureAuditorToken(page);
    if (auditorToken !== null) {
      headers = { Authorization: `Bearer ${auditorToken}` };
      identityUsed = 'auditor';
    } else {
      // Auditor unavailable — fall back to primary token. On environments
      // where the primary user has audit-read (local dev with permissive
      // seeding) this still works; on stricter envs the GET will 403 and
      // the fetcher below surfaces the aggregated diagnostic.
      headers = await extractBearerHeaders(page);
      identityUsed = 'primary';
    }
  }

  // Backend exposes the list at /api/v1/audit/audit-events/ (router register
  // r"audit-events" at hub/apps/audit/urls.py:11, mounted under
  // /api/v1/audit/ at hub/apps/api/urls.py:26).
  const endpoint = options.auditEndpoint ?? '/api/v1/audit/audit-events/';
  const params = new URLSearchParams({
    resource_id: expected.resourceId,
    action: expected.action,
    page_size: '5',
  });
  const url = `${endpoint}?${params.toString()}`;

  const fetcher: AuditEventFetcher = async () => {
    const res = await page.request.get(url, { headers });
    if (!res.ok()) {
      let preview = '';
      try {
        preview = (await res.text()).slice(0, 400);
      } catch {
        // intentional: verifyAuditEvent's retry loop tolerates transient list endpoint errors; the final failure is reported by the polling-budget exhaustion error.
        /* ignore */
      }
      // Enrich the error with the identity used + auditor-availability
      // diagnostic so "why 403" is self-evident from the test log alone.
      const identityHint =
        identityUsed === 'primary'
          ? ` [identity=primary; ${
              auditorFailureReason
                ? `auditor side channel unavailable: ${auditorFailureReason}`
                : 'auditor side channel disabled'
            }]`
          : ` [identity=${identityUsed}]`;
      throw new Error(
        `verifyAuditEvent: GET ${url} returned ${res.status()}.${identityHint} Body preview: ${preview}`,
      );
    }
    const body = (await res.json()) as { results?: AuditEventRow[] } | AuditEventRow[];
    if (Array.isArray(body)) return body;
    return body.results ?? [];
  };

  return pollForAuditEvent(fetcher, {
    ...expected,
    retryBudgetMs: options.retryBudgetMs,
    pollIntervalMs: options.pollIntervalMs,
  });
}
