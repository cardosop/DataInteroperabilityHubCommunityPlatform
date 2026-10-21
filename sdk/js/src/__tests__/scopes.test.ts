/**
 * W6.5 (S1) — scope vocabulary pins for the JS SDK.
 *
 * The parity against the BACKEND vocabulary is pinned by the python
 * contract test (scripts/tests/test_w65_scope_set_contract.py), which
 * parses src/scopes.ts.  This suite pins the BEHAVIOUR of the JS
 * module: validator semantics, role lookups, and the exported surface.
 */

import {
  ALL_SCOPES,
  ROLE_SCOPES,
  SCOPE_SCHEDULED_INGESTION_INTERNAL,
  WILDCARD_SCOPE,
  validateScopes,
  scopeSetForRole,
} from '../scopes';
import * as sdk from '../index';

describe('W6.5 — JS scope vocabulary', () => {
  it('exports the vocabulary from the package index', () => {
    expect(sdk.ALL_SCOPES).toEqual(ALL_SCOPES);
    expect(sdk.ROLE_SCOPES).toEqual(ROLE_SCOPES);
    expect(sdk.validateScopes).toBe(validateScopes);
    expect(sdk.scopeSetForRole).toBe(scopeSetForRole);
  });

  it('carries the wildcard and internal-scope constants', () => {
    expect(WILDCARD_SCOPE).toBe('*');
    expect(SCOPE_SCHEDULED_INGESTION_INTERNAL).toBe('scheduled_ingestion:internal');
    expect(ALL_SCOPES).not.toContain(SCOPE_SCHEDULED_INGESTION_INTERNAL);
    expect(ALL_SCOPES).not.toContain(WILDCARD_SCOPE);
  });

  it('covers every role scope in ALL_SCOPES', () => {
    for (const scopes of Object.values(ROLE_SCOPES)) {
      for (const scope of scopes) {
        if (scope !== WILDCARD_SCOPE) {
          expect(ALL_SCOPES).toContain(scope);
        }
      }
    }
  });

  it('validateScopes returns exactly the out-of-vocabulary scopes', () => {
    expect(validateScopes(['assets:read'])).toEqual([]);
    expect(validateScopes(['nope:nope'])).toEqual(['nope:nope']);
    expect(validateScopes([WILDCARD_SCOPE])).toEqual([]);
    expect(validateScopes(['assets:read', 'nope:nope', 'assets:read', 'nope:nope'])).toEqual([
      'nope:nope',
    ]);
  });

  it('validateScopes always flags the worker-internal scope', () => {
    expect(validateScopes([SCOPE_SCHEDULED_INGESTION_INTERNAL])).toEqual([
      SCOPE_SCHEDULED_INGESTION_INTERNAL,
    ]);
  });

  it('scopeSetForRole returns the role set and empty for unknown roles', () => {
    expect(scopeSetForRole('DATA_VIEWER')).toEqual([
      'assets:read',
      'contracts:read',
      'datasets:read',
    ]);
    expect(scopeSetForRole('PLATFORM_ADMIN')).toEqual([WILDCARD_SCOPE]);
    expect(scopeSetForRole('NO_SUCH_ROLE')).toEqual([]);
  });
});
