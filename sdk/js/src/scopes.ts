/**
 * JWT/API-key scope vocabulary carried by the SDK (W6.5, S1).
 *
 * This module is a CONTRACT COPY of the backend's vocabulary
 * (`hub.apps.auth.scopes` — the single source of truth).  The contract
 * test `scripts/tests/test_w65_scope_set_contract.py` parses this file
 * and pins it equal to the backend, so a scope change on either side
 * must land in the same change.  The W7.5 `ENFORCE_JWT_SCOPES` flip
 * depends on the platform's own clients carrying exactly this set.
 *
 * STRICT SHAPE CONTRACT: the python contract test parses this file with
 * a deterministic extractor.  Every declaration must keep the form
 * `export const NAME: <type> = <value>;` with single-quoted strings and
 * one array/object entry per line — reformatting breaks the contract
 * test (intentionally).
 */

/** Wildcard scope: grants everything. PLATFORM_ADMIN-only to mint. */
export const WILDCARD_SCOPE = '*';

/** Worker-internal scope — NEVER mintable via the public API (R2-B2). */
export const SCOPE_SCHEDULED_INGESTION_INTERNAL = 'scheduled_ingestion:internal';

/** Role → granted scopes (mirrors the backend ROLE_SCOPE_MAP). */
export const ROLE_SCOPES: Record<string, readonly string[]> = {
  PLATFORM_ADMIN: [
    '*',
  ],
  TENANT_ADMIN: [
    'assets:read',
    'assets:write',
    'contracts:read',
    'contracts:write',
    'datasets:read',
    'datasets:write',
    'compliance:read',
    'compliance:write',
    'governance:read',
    'governance:write',
    'users:read',
    'users:write',
    'billing:read',
    'billing:write',
    'audit:read',
    'files:read',
    'files:write',
    'jobs:read',
    'jobs:write',
    'marketplace:read',
    'marketplace:write',
    'mesh:read',
    'mesh:write',
    'integrations:read',
    'integrations:write',
    'ml:read',
    'ml:write',
    'transformation:read',
    'transformation:write',
    'virtualization:write',
  ],
  DATA_PROVIDER: [
    'assets:read',
    'assets:write',
    'contracts:read',
    'contracts:write',
    'datasets:read',
    'datasets:write',
    'files:read',
    'files:write',
    'jobs:read',
    'jobs:write',
    'marketplace:read',
    'marketplace:write',
    'mesh:read',
    'mesh:write',
    'integrations:read',
    'integrations:write',
    'ml:read',
    'ml:write',
    'transformation:read',
    'transformation:write',
    'virtualization:write',
  ],
  DATA_CONSUMER: [
    'assets:read',
    'contracts:read',
    'datasets:read',
    'files:read',
    'marketplace:read',
    'mesh:read',
    'ml:read',
    'transformation:read',
  ],
  DATA_VIEWER: [
    'assets:read',
    'contracts:read',
    'datasets:read',
  ],
  PII_VIEWER: [
    'assets:read',
    'contracts:read',
    'datasets:read',
    'datasets:view_pii',
  ],
  AUDITOR: [
    'audit:read',
    'compliance:read',
    'governance:read',
  ],
  COMPLIANCE_OFFICER: [
    'compliance:read',
    'compliance:write',
    'governance:read',
    'governance:write',
    'audit:read',
  ],
};

/** Every concrete scope in the vocabulary (wildcard and the internal
 * scope excluded). */
export const ALL_SCOPES: readonly string[] = [
  'assets:read',
  'assets:write',
  'contracts:read',
  'contracts:write',
  'datasets:read',
  'datasets:write',
  'datasets:view_pii',
  'compliance:read',
  'compliance:write',
  'governance:read',
  'governance:write',
  'users:read',
  'users:write',
  'billing:read',
  'billing:write',
  'audit:read',
  'files:read',
  'files:write',
  'jobs:read',
  'jobs:write',
  'marketplace:read',
  'marketplace:write',
  'mesh:read',
  'mesh:write',
  'integrations:read',
  'integrations:write',
  'ml:read',
  'ml:write',
  'transformation:read',
  'transformation:write',
  'virtualization:write',
];

/**
 * Return the scopes from `requested` that are NOT in the client
 * vocabulary, in input order, without duplicates.  The wildcard passes
 * (mintable by PLATFORM_ADMIN — the backend enforces the role gate);
 * the worker-internal scope is ALWAYS flagged (R2-B2).
 */
export function validateScopes(requested: readonly string[]): string[] {
  const invalid: string[] = [];
  const seen = new Set<string>();
  for (const scope of requested) {
    if (seen.has(scope)) {
      continue;
    }
    seen.add(scope);
    if (
      scope === SCOPE_SCHEDULED_INGESTION_INTERNAL ||
      (scope !== WILDCARD_SCOPE && !ALL_SCOPES.includes(scope))
    ) {
      invalid.push(scope);
    }
  }
  return invalid;
}

/** The scope set a role grants (empty for unknown roles). */
export function scopeSetForRole(role: string): readonly string[] {
  return ROLE_SCOPES[role] ?? [];
}
