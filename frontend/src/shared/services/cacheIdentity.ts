/**
 * W5.2 (oss-release-remediation R2-F2) — the identity-boundary cache bus.
 *
 * Every identity transition (login, logout, auth failure, tenant switch)
 * MUST invalidate the caches that hold identity-scoped data — the React
 * Query client (query keys are NOT tenant-scoped; a tenant B render must
 * never surface tenant A's cached rows) and the capabilities singleton
 * (the runtime snapshot is per-tenant).
 *
 * Consumers register invalidators HERE instead of importing each other
 * (the auth store must not import the React Query client — layering);
 * the auth store is the single place that fires the boundaries. The bus
 * is module-state only — no React, no imports, no cycles.
 */

export type CacheIdentityBoundary = 'login' | 'logout' | 'auth-failed' | 'tenant-switch';

type Invalidator = (boundary: CacheIdentityBoundary) => void;

const invalidators = new Set<Invalidator>();

/**
 * Register a cache invalidator. Returns the unregister function.
 * Idempotent per function reference (registering twice is a no-op).
 */
export function registerIdentityCacheInvalidator(invalidator: Invalidator): () => void {
  invalidators.add(invalidator);
  return () => {
    invalidators.delete(invalidator);
  };
}

/**
 * Fire an identity boundary: every registered invalidator runs.
 * A throwing invalidator must never break the boundary transition —
 * the invalidation is best-effort BY CONTRACT (the auth transition
 * itself carries the correctness; a crashed cache clear must not
 * strand the user half-logged-out).
 */
export function invalidateIdentityCaches(boundary: CacheIdentityBoundary): void {
  for (const invalidator of [...invalidators]) {
    try {
      invalidator(boundary);
    } catch (error) {
      console.warn(`identity cache invalidator failed (${boundary})`, error);
    }
  }
}

/** Test/tooling helper — how many invalidators are registered. */
export function identityCacheInvalidatorCount(): number {
  return invalidators.size;
}
