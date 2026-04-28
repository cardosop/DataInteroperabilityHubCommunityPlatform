/**
 * Phase 226 E2 — Shared `createdResources` tracker core.
 *
 * Extracts the per-test resource registry + REST teardown logic so it can
 * be wired into both `test-data-cleanup.ts` (existing fixture, used by API-
 * create journey specs) and `guardedTest.ts` (universal guard, gets the
 * tracker as an auto fixture so UI-create flows clean up by default).
 *
 * Why a shared module: before E2, only `test-data-cleanup.ts` exposed a
 * registry, and only API-create helpers wrote to it. UI-create flows
 * (form submit → 302 → list page) had no symmetric path and routinely
 * leaked rows, kept tidy only by the staging-side prefix-purge cron. By
 * making the tracker an auto fixture in `guardedTest.ts`, every spec that
 * already uses `guardedTest` (most of the suite, post-Track A) now has a
 * `createdResources` handle in scope without changing its imports.
 *
 * Why same teardown semantics as `cleanup`: the resource types, REST
 * verbs, owner-based re-login, and FK-respecting order are already
 * battle-tested in `test-data-cleanup.ts`. Diverging semantics would be
 * a footgun (two registries with different "DELETE means hard or soft?"
 * behaviors). This module exports the pure logic; the fixture wrappers
 * just plug it in.
 *
 * No mocks. Real backend only.
 */

import { randomUUID } from 'node:crypto';
import type { TestUser } from '../setup/create-test-user';
import { loginViaApi } from './auth';

/**
 * Per-process run identifier. Each Playwright worker is its own Node
 * process, so this gives a stable per-worker UUID that can be embedded
 * in resource names (`e2e-<run_id>-asset-foo`) for orphan triage on the
 * staging side. Re-exported by `test-data-cleanup.ts` as `E2E_RUN_ID`.
 */
export const E2E_RUN_ID = randomUUID();

export type CreatedResourceType =
  | 'asset'
  | 'contract'
  | 'listing'
  | 'dataset'
  | 'order'
  | 'user';

export interface CreatedResource {
  type: CreatedResourceType;
  id: string;
  /**
   * The user that owns the resource. We re-login as this user immediately
   * before teardown — long tests can outlive a 15-min access token, and
   * silent 401s during teardown would leak the row.
   */
  owner: TestUser;
}

export interface CreatedResourcesRegistry {
  /** Register a created resource for automatic teardown at test end. */
  track(resource: CreatedResource): void;
  /**
   * Manually flush teardown. Normally not called by tests — the fixture
   * auto-flushes after the test body completes. Exposed so a spec that
   * needs to verify cleanup happened mid-test can drive it explicitly.
   */
  flush(): Promise<TeardownResult>;
  /** Test-scoped run id (alias of `E2E_RUN_ID`). */
  readonly runId: string;
  /** Snapshot of currently tracked resources (for assertions in tests). */
  snapshot(): CreatedResource[];
}

export interface TeardownResult {
  attempted: number;
  succeeded: number;
  failures: string[];
}

// ---------------------------- pure logic (testable without HTTP) ----------

/** De-dupe key. A composite of `type:id` so tracking the same resource
 * twice is a no-op (e.g. helper tracks it AND the spec also tracks it
 * manually). */
function keyFor(r: CreatedResource): string {
  return `${r.type}:${r.id}`;
}

/**
 * Stable teardown order — orders first (so the listing they reference is
 * still alive), then datasets, then listings, then contracts, then
 * assets, then users. Reverse of typical creation order; respects FK
 * direction so cascade-delete on the parent doesn't fire 404s on the
 * child we'd queue next.
 */
export const TEARDOWN_ORDER: Record<CreatedResourceType, number> = {
  order: 0,
  dataset: 1,
  listing: 2,
  contract: 3,
  asset: 4,
  user: 5,
};

export function orderResources(resources: CreatedResource[]): CreatedResource[] {
  return [...resources].sort((a, b) => TEARDOWN_ORDER[a.type] - TEARDOWN_ORDER[b.type]);
}

/** Group by owner email so we re-login once per owner, not per resource. */
export function groupByOwner(
  resources: CreatedResource[],
): Map<string, CreatedResource[]> {
  const groups = new Map<string, CreatedResource[]>();
  for (const r of resources) {
    const key = r.owner.email;
    const list = groups.get(key);
    if (list) list.push(r);
    else groups.set(key, [r]);
  }
  return groups;
}

/**
 * Map a `CreatedResource` to its REST teardown shape. Returns `{ method,
 * url }` so the caller can do the actual fetch (or stub it for tests).
 */
export function teardownRequestFor(
  resource: CreatedResource,
  apiBase: string,
): { method: 'DELETE' | 'POST'; url: string } {
  const base = apiBase.replace(/\/$/, '');
  switch (resource.type) {
    case 'asset':
      return { method: 'DELETE', url: `${base}/assets/${resource.id}/` };
    case 'contract':
      return { method: 'DELETE', url: `${base}/contracts/${resource.id}/` };
    case 'listing':
      return { method: 'DELETE', url: `${base}/marketplace/listings/${resource.id}/` };
    case 'dataset':
      return { method: 'DELETE', url: `${base}/datasets/${resource.id}/` };
    case 'order':
      // POST /cancel/ is the idiomatic transition to CANCELLED; bare DELETE would
      // hard-delete and lose the audit trail (213.C.1 audit findings).
      return { method: 'POST', url: `${base}/marketplace/orders/${resource.id}/cancel/` };
    case 'user':
      return { method: 'DELETE', url: `${base}/users/${resource.id}/` };
    default: {
      const _exhaustive: never = resource.type;
      throw new Error(`teardownRequestFor: unknown resource type ${_exhaustive as string}`);
    }
  }
}

// ----------------------------- API-base resolution ------------------------

function resolveApiBase(env: Record<string, string | undefined>): string {
  const defaultPort = env.E2E_WEB_PORT ? '8001' : '8000';
  const fromExplicit = env.E2E_API_BASE_URL;
  if (fromExplicit) return fromExplicit;
  const fromProxy = env.VITE_PROXY_TARGET;
  if (fromProxy) return `${fromProxy.replace(/\/$/, '')}/api/v1`;
  const fromVite = env.VITE_API_BASE_URL;
  if (fromVite && fromVite.startsWith('http')) return fromVite;
  return `http://localhost:${defaultPort}/api/v1`;
}

// ------------------------------ HTTP teardown -----------------------------

interface TeardownDeps {
  /** Defaults to global `fetch`. Injectable so unit tests can stub. */
  fetchImpl?: typeof fetch;
  /** Defaults to `loginViaApi`. Injectable for unit tests. */
  loginImpl?: (
    email: string,
    password: string,
  ) => Promise<{ access_token: string }>;
  /** Defaults to `process.env`. */
  env?: Record<string, string | undefined>;
}

/**
 * Tear down every tracked resource using the supplied (or default) HTTP
 * client. Returns a result object so callers can decide how to surface
 * failures (annotation, console, throw).
 */
export async function teardownAll(
  resources: CreatedResource[],
  deps: TeardownDeps = {},
): Promise<TeardownResult> {
  const env = deps.env ?? process.env;
  const fetchImpl = deps.fetchImpl ?? fetch;
  const loginImpl = deps.loginImpl ?? loginViaApi;
  const apiBase = resolveApiBase(env);

  const ordered = orderResources(resources);
  const groups = groupByOwner(ordered);

  let attempted = 0;
  let succeeded = 0;
  const failures: string[] = [];

  for (const [, ownerResources] of groups) {
    const owner = ownerResources[0].owner;
    let token: string;
    try {
      const auth = await loginImpl(owner.email, owner.password);
      token = auth.access_token;
    } catch (err) {
      failures.push(
        `createdResources: re-login failed for owner ${owner.email}: ${(err as Error).message}`,
      );
      continue;
    }
    for (const r of ownerResources) {
      attempted++;
      const { method, url } = teardownRequestFor(r, apiBase);
      try {
        const res = await fetchImpl(url, {
          method,
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
        });
        if (res.ok || res.status === 404) {
          succeeded++;
          continue;
        }
        // intentional: best-effort body read for diagnostic context only;
        // the throw below is the primary failure path.
        const body = await res.text().catch(() => '');
        failures.push(
          `createdResources: teardown ${r.type}/${r.id} → ${res.status} ${body.slice(0, 200)}`,
        );
      } catch (err) {
        failures.push(
          `createdResources: teardown ${r.type}/${r.id} threw: ${(err as Error).message}`,
        );
      }
    }
  }
  return { attempted, succeeded, failures };
}

// ------------------------------- registry factory ------------------------

/**
 * Construct a fresh per-test registry. The fixture wrappers (in
 * `test-data-cleanup.ts` and `guardedTest.ts`) call this once per test
 * and pass the resulting registry into `await use(registry)`.
 */
export function createRegistry(deps: TeardownDeps = {}): CreatedResourcesRegistry {
  const tracked: CreatedResource[] = [];
  return {
    runId: E2E_RUN_ID,
    snapshot() {
      return tracked.slice();
    },
    track(resource) {
      const k = keyFor(resource);
      if (tracked.some((r) => keyFor(r) === k)) return;
      tracked.push(resource);
    },
    async flush() {
      if (tracked.length === 0) {
        return { attempted: 0, succeeded: 0, failures: [] };
      }
      const snapshot = tracked.slice();
      tracked.length = 0;
      return teardownAll(snapshot, deps);
    },
  };
}
