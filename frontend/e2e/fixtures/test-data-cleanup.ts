/**
 * E2E test-data cleanup fixture (Phase 213.C, Option A).
 *
 * Provides a per-test `cleanup` registry exposed via Playwright `test.extend()` so that
 * mutating journey specs can `cleanup.track({ type, id, owner })` immediately after
 * creating a backend resource. After the test body finishes (success OR failure), the
 * fixture re-logs-in as each unique owner and tears resources down via the appropriate
 * REST verb for that resource type.
 *
 * Why a fixture (not a module singleton): test-scoped fixtures are isolated per worker
 * and per test. A module singleton would leak state between parallel tests in the same
 * worker and would have no auto-teardown hook on test failure.
 *
 * Why re-login on teardown: long-running tests (DPO-001 = 6 min) can outlive the access
 * token captured at the start of the test, so we cannot reuse the original token. We
 * fetch a fresh one immediately before issuing DELETE/cancel calls.
 *
 * Per-resource-type strategy (revised after the 213.C.1 backend audit):
 *   - asset    → DELETE  (soft, status→RETIRED)
 *   - contract → DELETE  (soft, status→RETIRED)
 *   - listing  → DELETE  (soft, status→DELETED)
 *   - dataset  → DELETE  (HARD)
 *   - order    → POST /orders/{id}/cancel/  (soft, status→CANCELLED)
 *   - user     → DELETE  (conditional: soft→DISABLED if owns resources, otherwise HARD)
 *
 * "Orphan" is redefined to mean an `e2e-`/`E2E `-prefixed row whose status is NOT in
 * (RETIRED, DELETED, DISABLED, CANCELLED). Acceptance check 213.C.11 was updated
 * accordingly. RETIRED/DELETED/DISABLED rows are tombstones — they're audit-trail
 * artifacts (and marketplace entitlement tombstones) preserved deliberately by the
 * service layer. A separate periodic vacuum management command is parked for later.
 *
 * No mocks. Real backend only.
 */

import { test as base } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import type { TestUser } from '../setup/create-test-user';
import { loginViaApi } from './auth';

/**
 * Per-process run identifier. Each Playwright worker is its own Node process, so this
 * gives a stable per-worker UUID that can be embedded in resource names for orphan
 * triage (`name__startswith='e2e-<run_id>'`). Use it via `${E2E_RUN_ID}` in spec code
 * when generating resource names that need to be traceable across CI runs.
 */
export const E2E_RUN_ID = randomUUID();

/** Resource types the cleanup fixture knows how to tear down. */
export type CleanupResourceType =
  | 'asset'
  | 'contract'
  | 'listing'
  | 'dataset'
  | 'order'
  | 'user';

export interface CleanupResource {
  type: CleanupResourceType;
  id: string;
  /**
   * The user that owns the resource (i.e. who can delete it). The fixture re-logs-in
   * as this user immediately before teardown so an expired access token mid-test does
   * not silently break cleanup.
   */
  owner: TestUser;
}

export interface CleanupRegistry {
  /** Register a created resource for automatic teardown at test end. */
  track(resource: CleanupResource): void;
  /**
   * Manually flush teardown. Normally not called by tests — the fixture flushes
   * automatically after the test body finishes. Exposed for tests that need to
   * verify cleanup happened mid-test.
   */
  flush(): Promise<void>;
  /** The per-process run id (alias of `E2E_RUN_ID`); convenient for in-test name tagging. */
  readonly runId: string;
}

// API base URL resolution mirrors auth.ts/api-assets.ts so the fixture works with both
// local (8000/8001) and external targets (meshant-internal.example.com) without extra config.
const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http')
    ? process.env.VITE_API_BASE_URL
    : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

/**
 * Resource-type → REST call mapping. Each strategy returns void on success and
 * throws on hard failure. 404 is treated as success (the resource was already
 * gone — likely cleaned up by a cascade or a previous teardown).
 */
async function teardownOne(resource: CleanupResource, accessToken: string): Promise<void> {
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${accessToken}`,
  };

  let url: string;
  let method: 'DELETE' | 'POST';

  switch (resource.type) {
    case 'asset':
      url = `${API_BASE}/assets/${resource.id}/`;
      method = 'DELETE';
      break;
    case 'contract':
      url = `${API_BASE}/contracts/${resource.id}/`;
      method = 'DELETE';
      break;
    case 'listing':
      url = `${API_BASE}/marketplace/listings/${resource.id}/`;
      method = 'DELETE';
      break;
    case 'dataset':
      url = `${API_BASE}/datasets/${resource.id}/`;
      method = 'DELETE';
      break;
    case 'order':
      // POST /cancel/ is the idiomatic transition to CANCELLED. Bare DELETE would
      // hard-delete and lose the audit trail (see 213.C.1 audit findings).
      url = `${API_BASE}/marketplace/orders/${resource.id}/cancel/`;
      method = 'POST';
      break;
    case 'user':
      // Conditional inside the backend: soft (status→DISABLED) if user owns resources,
      // hard-delete otherwise. Either outcome satisfies "no active orphan".
      url = `${API_BASE}/users/${resource.id}/`;
      method = 'DELETE';
      break;
    default: {
      // Exhaustiveness check — if a new resource type is added to the union but not
      // here, TypeScript will catch it at compile time.
      const _exhaustive: never = resource.type;
      throw new Error(`teardownOne: unknown resource type ${_exhaustive}`);
    }
  }

  const res = await fetch(url, { method, headers });
  // 204 No Content (typical DELETE), 200 OK (typical cancel), 404 Not Found are all OK.
  if (res.ok || res.status === 404) return;
  const body = await res.text().catch(() => '');
  throw new Error(
    `cleanup.teardown ${resource.type}/${resource.id} failed: ${res.status} ${body.slice(0, 200)}`
  );
}

/**
 * Group resources by owner email so we only re-login once per distinct owner during
 * teardown (instead of once per resource — would saturate the auth rate limiter on
 * tests that create many resources).
 */
function groupByOwner(resources: CleanupResource[]): Map<string, CleanupResource[]> {
  const groups = new Map<string, CleanupResource[]>();
  for (const r of resources) {
    const key = r.owner.email;
    const list = groups.get(key);
    if (list) list.push(r);
    else groups.set(key, [r]);
  }
  return groups;
}

/**
 * Stable teardown order: orders first (so the listing they reference is still alive),
 * then datasets, then listings, then contracts, then assets, then users. Reverse of
 * typical creation order; respects FK direction.
 */
const TEARDOWN_ORDER: Record<CleanupResourceType, number> = {
  order: 0,
  dataset: 1,
  listing: 2,
  contract: 3,
  asset: 4,
  user: 5,
};

function orderResources(resources: CleanupResource[]): CleanupResource[] {
  return [...resources].sort((a, b) => TEARDOWN_ORDER[a.type] - TEARDOWN_ORDER[b.type]);
}

/**
 * Playwright test extended with a per-test `cleanup` fixture. Import this `test` (and
 * the re-exported `expect`) instead of the bare `@playwright/test` exports in any
 * journey spec that creates mutating backend resources.
 *
 * Usage:
 *   import { test, expect } from '../../fixtures/test-data-cleanup';
 *   test('foo', async ({ page, cleanup }) => {
 *     const id = await createAssetViaApi(user, { cleanup });   // helper-side tracking
 *     // …or, if not using a helper that supports cleanup:
 *     cleanup.track({ type: 'asset', id, owner: user });
 *   });
 */
export const test = base.extend<{ cleanup: CleanupRegistry }>({
  cleanup: async ({}, use, testInfo) => {
    const tracked: CleanupResource[] = [];

    const registry: CleanupRegistry = {
      runId: E2E_RUN_ID,
      track(resource) {
        // De-dupe by composite key. Some helpers may track the same id twice (e.g. when
        // a "get-or-create" helper reuses an existing resource and the spec also tracks
        // it manually).
        const key = `${resource.type}:${resource.id}`;
        if (tracked.some((r) => `${r.type}:${r.id}` === key)) return;
        tracked.push(resource);
      },
      async flush() {
        if (tracked.length === 0) return;
        const ordered = orderResources(tracked);
        const groups = groupByOwner(ordered);

        const failures: string[] = [];
        for (const [, ownerResources] of groups) {
          const owner = ownerResources[0].owner;
          let token: string;
          try {
            // Re-login: do NOT reuse a token captured at test start — long tests can
            // outlive token TTL (15 min default), and 401 during teardown is silent.
            const auth = await loginViaApi(owner.email, owner.password);
            token = auth.access_token;
          } catch (err) {
            failures.push(
              `cleanup: re-login failed for owner ${owner.email}: ${(err as Error).message}`
            );
            continue;
          }
          for (const r of ownerResources) {
            try {
              await teardownOne(r, token);
            } catch (err) {
              failures.push((err as Error).message);
            }
          }
        }

        // Clear so a manual flush() does not double-process. The fixture's auto-flush
        // (below) will then no-op.
        tracked.length = 0;

        if (failures.length > 0) {
          // Surface cleanup failures as test annotations rather than throwing — the
          // test body has already finished, and throwing here would mask the original
          // failure (if any). Annotations are visible in the HTML report and JSON.
          testInfo.annotations.push({
            type: 'cleanup-failed',
            description: `Phase 213.C cleanup encountered ${failures.length} failure(s):\n${failures.join('\n')}`,
          });
        }
      },
    };

    await use(registry);

    // Auto-flush after the test body completes (success OR failure). Wrapped in
    // try/catch so a teardown error never replaces the original test failure.
    try {
      await registry.flush();
    } catch (err) {
      testInfo.annotations.push({
        type: 'cleanup-failed',
        description: `Phase 213.C cleanup auto-flush threw: ${(err as Error).message}`,
      });
    }
  },
});

export { expect } from '@playwright/test';
