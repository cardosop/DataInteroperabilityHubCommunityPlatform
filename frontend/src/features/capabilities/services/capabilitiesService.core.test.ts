/**
 * Phase 313.4 — core-only capability derivation (pure function, real fixtures).
 *
 * Locks the open-core contract: against a HUB_CORE_ONLY=1 backend, every
 * paid capability resolves `available: false` and every core capability
 * stays available — the frontend then hides paid UI via CapabilityRoute
 * and shows the /coming-soon page instead.
 */

import { describe, expect, it } from 'vitest';

import { capabilitiesService } from './capabilitiesService';
import type { OpenAPISchema } from '../../../shared/types/capabilities';

// A minimal core-only OpenAPI fixture: core paths only, zero paid paths.
// TS `private` is compile-time only; the derivation method is pure
// (no `this` usage) — bracket access is the typed way to reach it without
// an `any` cast or a mock.
function derive(schema: OpenAPISchema) {
  return capabilitiesService['deriveCapabilitiesFromOpenAPI'](schema);
}

function coreOnlySchema(): OpenAPISchema {
  return {
    openapi: '3.0.3',
    info: { title: 'core', version: '1' },
    paths: {
      '/api/v1/auth/register/': {},
      '/api/v1/auth/password-reset/': {},
      '/api/v1/assets/': {},
      '/api/v1/datasets/': {},
      '/api/v1/contracts/': {},
      '/api/v1/dq/runs/': {},
      '/api/v1/compliance/runs/': {},
      '/api/v1/search/': {},
      '/api/v1/tenants/me/': {},
    },
  };
}

const PAID_KEYS = [
  'semantic.sparql',
  'social.ratings',
  'lineage.cross_tenant_marketplace',
  'ai.natural-language-search',
  'ai.schema-matching',
];

describe('core-only capability derivation', () => {
  it('resolves paid capabilities as unavailable against a core-only schema', () => {
    const caps = derive(coreOnlySchema());
    for (const key of PAID_KEYS) {
      expect(caps[key]?.available ?? false, `${key} must be unavailable`).toBe(false);
    }
  });

  it('keeps core capabilities available against a core-only schema', () => {
    const caps = derive(coreOnlySchema());
    expect(caps['auth.register']?.available).toBe(true);
    expect(caps['auth.password-reset']?.available).toBe(true);
  });
});
