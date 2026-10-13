/**
 * Capabilities Service
 * Derives capabilities from OpenAPI presence and optional runtime probe
 */

import { apiClient } from '../../../shared/api/client';
import type {
  AssetCreationBlockedReason,
  CapabilitiesMap,
  Capability,
  OpenAPISchema,
  RuntimeCapabilitiesSnapshot,
} from '../../../shared/types/capabilities';

const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

/**
 * Path-derived capability definition (313.H.4 registry).
 *
 * Single source of truth for every capability the SPA derives from the
 * OpenAPI schema. ``samplePaths`` are the canonical paths that MUST make
 * the capability available — the drift test (paidRouteDrift.test.tsx)
 * builds a synthetic schema from them and asserts every definition
 * resolves ``available: true`` (a dead predicate would silently disable
 * the feature in FULL mode).
 */
export interface CapabilityDefinition {
  key: string;
  name: string;
  endpoint: string;
  operationId?: string;
  samplePaths: string[];
  isPathIncluded: (paths: Record<string, unknown>) => boolean;
}

/** Capability keys sourced from the RUNTIME snapshot (GET /capabilities/),
 *  not from OpenAPI paths. Enumerated so the drift test covers them too. */
export const RUNTIME_CAPABILITY_KEYS: readonly string[] = [
  'asset_creation',
  'datasets',
  'files',
  'data_quality',
  'data_quality_advanced',
  'compliance_consent',
  'compliance_ropa',
  'compliance_dpia',
  'compliance_retention_enforcer',
  'compliance_dsar',
  'compliance_breach',
  'compliance_processor_agreements',
  // Phase 228 F5/F3 — settings-side lineage flags overlaid from the
  // runtime snapshot (never path-derived; see refreshRuntimeSnapshot).
  'lineage.snapshots',
  'lineage.change_notifications',
  // openspec add-databricks-control-plane P0 — runtime-sourced (the backend
  // /capabilities/ view emits it from databricks_control_plane_enabled);
  // registered in ALL_CAPABILITY_KEYS so the paidRouteDrift enumeration
  // covers the /databricks CapabilityRoute gates.
  'databricks',
  // Phase 278.R.6 (close-test-coverage-gaps 3.2) — UX v2 staged rollout;
  // runtime-sourced from Tenant.ux_v2_enabled. The ProductTourGate reads
  // it; without the registration the gate resolved ?? false for every
  // tenant and the product tour never mounted.
  'ux_v2',
  // plan_compliance_pro_pack is NOT a runtime capability: its source is the
  // subscription plan on /me (hub/apps/tenants/views.py). Declaring it here
  // made the registry claim a wire key the capabilities endpoint never emits
  // — pinned by test_anonymous_wire_contract_is_exact_and_pinned (backend).
];

const pathKeys = (paths: Record<string, unknown>): string[] => Object.keys(paths);
const hasPath = (paths: Record<string, unknown>, exact: string): boolean => exact in paths;
const anyPath = (paths: Record<string, unknown>, pred: (p: string) => boolean): boolean =>
  pathKeys(paths).some(pred);

export const CAPABILITY_DEFINITIONS: readonly CapabilityDefinition[] = [
  {
    key: 'auth.register',
    name: 'User Registration',
    endpoint: '/api/v1/auth/register/',
    operationId: 'auth_register_create',
    samplePaths: ['/api/v1/auth/register/'],
    // Support both /api/v1/auth/... and /auth/... formats (drf-spectacular may vary)
    isPathIncluded: (paths) =>
      hasPath(paths, '/api/v1/auth/register/') ||
      anyPath(paths, (p) => p.includes('auth/register') && p.endsWith('auth/register/')),
  },
  {
    key: 'auth.password-reset',
    name: 'Password Reset Request',
    endpoint: '/api/v1/auth/password-reset/',
    operationId: 'auth_password_reset_create',
    samplePaths: ['/api/v1/auth/password-reset/'],
    isPathIncluded: (paths) =>
      hasPath(paths, '/api/v1/auth/password-reset/') ||
      anyPath(paths, (p) => p.includes('auth/password-reset') && !p.includes('confirm')),
  },
  {
    key: 'auth.password-reset-confirm',
    name: 'Password Reset Confirmation',
    endpoint: '/api/v1/auth/password-reset/confirm/',
    operationId: 'auth_password_reset_confirm_create',
    samplePaths: ['/api/v1/auth/password-reset/confirm/'],
    isPathIncluded: (paths) =>
      hasPath(paths, '/api/v1/auth/password-reset/confirm/') ||
      anyPath(paths, (p) => p.includes('auth/password-reset') && p.includes('confirm')),
  },
  {
    key: 'ai.natural-language-search',
    name: 'AI Natural Language Search',
    endpoint: '/api/v1/ai/natural-language-search/',
    operationId: 'natural_language_search',
    samplePaths: ['/api/v1/ai/natural-language-search/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/ai/natural-language-search/'),
  },
  {
    key: 'ai.schema-matching',
    name: 'AI Schema Matching',
    endpoint: '/api/v1/ai/schema-matching/',
    operationId: 'schema_matching',
    samplePaths: ['/api/v1/ai/schema-matching/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/ai/schema-matching/'),
  },
  {
    // Phase 273.1 — /search is permanently MVP-in-scope; the canonical endpoint.
    key: 'search.full-text',
    name: 'Full-Text Search',
    endpoint: '/api/search/',
    operationId: 'unified_search',
    samplePaths: ['/api/search/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/search/'),
  },
  {
    key: 'semantic.sparql',
    name: 'Semantic SPARQL',
    endpoint: '/api/v1/semantic/sparql',
    operationId: 'sparql_query',
    samplePaths: ['/api/v1/semantic/sparql'],
    isPathIncluded: (paths) =>
      hasPath(paths, '/api/v1/semantic/sparql') ||
      anyPath(paths, (p) => p.includes('semantic/sparql')),
  },
  {
    key: 'ai.classification',
    name: 'AI Classification',
    endpoint: '/api/v1/ai/classification/',
    samplePaths: ['/api/v1/ai/classification/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/ai/classification/'),
  },
  {
    key: 'ai.recommendations',
    name: 'AI Recommendations',
    endpoint: '/api/v1/ai/recommendations/',
    samplePaths: ['/api/v1/ai/recommendations/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/ai/recommendations/'),
  },
  {
    key: 'ai.anomaly-detection',
    name: 'AI Anomaly Detection',
    endpoint: '/api/v1/ai/anomaly-detection/',
    samplePaths: ['/api/v1/ai/anomaly-detection/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/ai/anomaly-detection/'),
  },
  {
    // Phase 228.F1 — per-listing lineage action; accept {id}/{listing_id} placeholders.
    key: 'lineage.cross_tenant_marketplace',
    name: 'Cross-Tenant Marketplace Lineage',
    endpoint: '/api/v1/marketplace/listings/{id}/lineage/',
    operationId: 'listing_lineage',
    samplePaths: ['/api/v1/marketplace/listings/{id}/lineage/'],
    isPathIncluded: (paths) =>
      anyPath(paths, (p) => /\/marketplace\/listings\/\{[^}]+\}\/lineage\/?$/.test(p)),
  },
  {
    // Phase 228.F2.32 — PATCH on the per-contract lineage path.
    key: 'contracts.lineage_field_editor',
    name: 'Field-Level Lineage Editor',
    endpoint: '/api/v1/contracts/{id}/lineage/',
    operationId: 'contract_lineage_edit',
    samplePaths: ['/api/v1/contracts/{id}/lineage/'],
    isPathIncluded: (paths) =>
      anyPath(paths, (p) => {
        if (!/\/contracts\/\{[^}]+\}\/lineage\/?$/.test(p)) return false;
        const ops = paths[p];
        return Boolean(ops && typeof ops === 'object' && 'patch' in (ops as object));
      }),
  },
  {
    key: 'social.ratings',
    name: 'Social Ratings',
    endpoint: '/api/v1/social/ratings/',
    samplePaths: ['/api/v1/social/ratings/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/social/ratings/'),
  },
  {
    key: 'social.reviews',
    name: 'Social Reviews',
    endpoint: '/api/v1/social/reviews/',
    samplePaths: ['/api/v1/social/reviews/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/social/reviews/'),
  },
  {
    key: 'social.comments',
    name: 'Social Comments',
    endpoint: '/api/v1/social/comments/',
    samplePaths: ['/api/v1/social/comments/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/social/comments/'),
  },
  {
    key: 'social.communities',
    name: 'Social Communities',
    endpoint: '/api/v1/social/communities/',
    samplePaths: ['/api/v1/social/communities/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/social/communities/'),
  },
  {
    key: 'social.activity-feeds',
    name: 'Social Activity Feeds',
    endpoint: '/api/v1/social/activity-feeds/',
    samplePaths: ['/api/v1/social/activity-feeds/'],
    // The route is /api/v1/social/activity-feeds/ (hyphenated "feeds") —
    // a "/feed" substring can never match it, which kept this capability
    // permanently false in the parity fallback (b6 skip root cause).
    isPathIncluded: (paths) =>
      hasPath(paths, '/api/v1/social/activity-feeds/') ||
      anyPath(paths, (p) => p.includes('social/activity-feeds')),
  },
  {
    key: 'developer.plugins',
    name: 'Developer Plugins',
    endpoint: '/api/v1/developer/plugins/',
    samplePaths: ['/api/v1/developer/plugins/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/developer/plugins/'),
  },
  {
    key: 'developer.sdk',
    name: 'Developer SDK Documentation',
    endpoint: '/api/v1/developer/sdk/',
    samplePaths: ['/api/v1/developer/sdk/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/developer/sdk/'),
  },
  {
    key: 'baas.api-keys',
    name: 'BaaS API Keys',
    endpoint: '/api/v1/baas/api-keys/',
    samplePaths: ['/api/v1/baas/api-keys/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/baas/api-keys/'),
  },
  {
    key: 'baas.usage',
    name: 'BaaS Usage Tracking',
    endpoint: '/api/v1/baas/usage/',
    samplePaths: ['/api/v1/baas/usage/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/baas/usage/'),
  },
  {
    key: 'ml.models',
    name: 'ML Models',
    endpoint: '/api/v1/ml/models/',
    samplePaths: ['/api/v1/ml/models/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/ml/models/'),
  },
  {
    key: 'ml.training',
    name: 'ML Training Jobs',
    endpoint: '/api/v1/ml/training/jobs/',
    samplePaths: ['/api/v1/ml/training/jobs/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/ml/training/jobs/'),
  },
  {
    key: 'ml.inference',
    name: 'ML Inference Deployments',
    endpoint: '/api/v1/ml/inference/deployments/',
    samplePaths: ['/api/v1/ml/inference/deployments/'],
    isPathIncluded: (paths) => hasPath(paths, '/api/v1/ml/inference/deployments/'),
  },
  {
    key: 'transformation',
    name: 'Transformation',
    endpoint: '/api/v1/transformation/pipelines/',
    samplePaths: ['/api/v1/transformation/pipelines/'],
    isPathIncluded: (paths) =>
      hasPath(paths, '/api/v1/transformation/pipelines/') ||
      anyPath(
        paths,
        (p) => p.includes('transformation/pipelines') || p.includes('transformation.pipelines')
      ),
  },
  {
    key: 'transformation.pipelines',
    name: 'Transformation Pipelines',
    endpoint: '/api/v1/transformation/pipelines/',
    samplePaths: ['/api/v1/transformation/pipelines/'],
    isPathIncluded: (paths) =>
      hasPath(paths, '/api/v1/transformation/pipelines/') ||
      anyPath(
        paths,
        (p) => p.includes('transformation/pipelines') || p.includes('transformation.pipelines')
      ),
  },
  {
    key: 'mesh.domains',
    name: 'Data Mesh Domains',
    endpoint: '/api/v1/mesh/domains/',
    samplePaths: ['/api/v1/mesh/domains/'],
    isPathIncluded: (paths) =>
      hasPath(paths, '/api/v1/mesh/domains/') || anyPath(paths, (p) => p.includes('/mesh/domains')),
  },
  {
    key: 'virtualization.datasets',
    name: 'Virtualization Datasets',
    endpoint: '/api/v1/virtualization/datasets/',
    samplePaths: ['/api/v1/virtualization/datasets/'],
    isPathIncluded: (paths) =>
      hasPath(paths, '/api/v1/virtualization/datasets/') ||
      anyPath(paths, (p) => p.includes('/virtualization/datasets')),
  },
  {
    key: 'integrations.marketplace',
    name: 'Marketplace Integrations',
    endpoint: '/api/v1/integrations/marketplace/connections/',
    samplePaths: ['/api/v1/integrations/marketplace/connections/'],
    isPathIncluded: (paths) =>
      hasPath(paths, '/api/v1/integrations/marketplace/connections/') ||
      anyPath(paths, (p) => p.includes('/integrations/') && p.includes('marketplace')),
  },
  {
    key: 'compliance_retention_enforcer',
    name: 'Retention auto-enforcement',
    endpoint: '/api/v1/governance/retention-policies/dashboard/',
    samplePaths: ['/api/v1/governance/retention-policies/dashboard/'],
    isPathIncluded: (paths) =>
      anyPath(
        paths,
        (p) => p.includes('/governance/retention-policies') && p.includes('dashboard')
      ),
  },
  {
    // Phase 260.3.B — Hub datasets REST (NOT virtualization.datasets).
    key: 'datasets',
    name: 'Datasets',
    endpoint: '/api/v1/datasets/',
    samplePaths: ['/api/v1/datasets/'],
    isPathIncluded: (paths) =>
      hasPath(paths, '/api/v1/datasets/') ||
      anyPath(
        paths,
        (p) => /\/api\/v1\/datasets\//.test(p) && !p.toLowerCase().includes('/virtualization/')
      ),
  },
  {
    key: 'files',
    name: 'Files',
    endpoint: '/api/v1/files/',
    samplePaths: ['/api/v1/files/'],
    isPathIncluded: (paths) =>
      hasPath(paths, '/api/v1/files/') || anyPath(paths, (p) => /\/api\/v1\/files\//.test(p)),
  },
  {
    // 313.H.4 — marketplace paid surface (routes.tsx /marketplace subtree).
    key: 'marketplace',
    name: 'Marketplace',
    endpoint: '/api/v1/marketplace/listings/',
    samplePaths: ['/api/v1/marketplace/listings/'],
    isPathIncluded: (paths) => anyPath(paths, (p) => p.includes('/api/v1/marketplace/')),
  },
  {
    // 313.H.4 — billing paid surface (subscription, plans, invoices,
    // admin cost-overview). Stripe Connect gets its own key below.
    key: 'billing',
    name: 'Billing',
    endpoint: '/api/v1/billing/subscription/',
    samplePaths: ['/api/v1/billing/subscription/'],
    isPathIncluded: (paths) =>
      anyPath(paths, (p) => p.startsWith('/api/v1/billing/') && !p.includes('/connect/')),
  },
  {
    // 313.H.4 — Stripe Connect surface (onboarding, payouts, KYB queue).
    key: 'billing.stripe_connect',
    name: 'Stripe Connect',
    endpoint: '/api/v1/billing/connect/status/',
    samplePaths: ['/api/v1/billing/connect/status/'],
    isPathIncluded: (paths) => anyPath(paths, (p) => p.includes('/api/v1/billing/connect/')),
  },
];

/** Every capability key the SPA can reference (path-derived + runtime). */
export const ALL_CAPABILITY_KEYS: ReadonlySet<string> = new Set([
  ...CAPABILITY_DEFINITIONS.map((d) => d.key),
  ...RUNTIME_CAPABILITY_KEYS,
]);

/**
 * Pure derivation: schema paths → CapabilitiesMap (data-driven via
 * CAPABILITY_DEFINITIONS). Exported for the drift test and used by the
 * service singleton.
 */
export function deriveCapabilitiesFromOpenAPI(schema: OpenAPISchema): CapabilitiesMap {
  const capabilities: CapabilitiesMap = {};
  const paths = (schema.paths ?? {}) as Record<string, unknown>;
  for (const def of CAPABILITY_DEFINITIONS) {
    capabilities[def.key] = {
      name: def.name,
      available: def.isPathIncluded(paths),
      endpoint: def.endpoint,
      ...(def.operationId ? { operationId: def.operationId } : {}),
    };
  }
  return capabilities;
}

class CapabilitiesService {
  private capabilities: CapabilitiesMap = {};
  private openApiSchema: OpenAPISchema | null = null;
  private cachedAt = 0;
  // Phase 250.6.D.2 — runtime capabilities snapshot (per-tenant).
  // Fetched alongside the OpenAPI schema; null until first fetch.
  private runtimeSnapshot: RuntimeCapabilitiesSnapshot | null = null;

  /**
   * Load path-derived capabilities and derive the full map.
   *
   * Primary source: GET /api/v1/capabilities/manifest/ — a ~2 KB map the
   * backend precomputes from the same drf-spectacular schema the OpenAPI
   * derivation below uses (hub/apps/api/capabilities.py, parity-audited
   * key-for-key). Fetching the 19.7 MB openapi.json on every fresh mount
   * was the root cause of the E2E gate-stall/bounce family (minutes-long
   * "Loading…" spinners and spurious /unavailable redirects under batch
   * load). Fallback: the previous OpenAPI-derivation flow, unchanged, for
   * backends without the manifest route.
   */
  async loadCapabilities(forceRefresh = false): Promise<CapabilitiesMap> {
    // Check in-memory cache first (no localStorage — prevents client-side manipulation)
    if (!forceRefresh && this.cachedAt > 0 && Date.now() - this.cachedAt < CACHE_TTL) {
      return this.capabilities;
    }
    // Manifest-first: on ANY failure (404 on old backends, network, parse)
    // fall through to the OpenAPI derivation with the existing retry logic.
    try {
      const manifest = await this._loadManifestCapabilities();
      if (manifest) {
        return manifest;
      }
    } catch {
      // Fall through to the OpenAPI path below — identical to pre-manifest
      // behaviour; a missing manifest must never change capability answers.
    }
    // One last-chance retry for a FULL failure (the first-pass fetch threw,
    // not just the runtime snapshot): a transient OpenAPI hiccup during a
    // fresh app mount otherwise downgrades the session to the auth-only
    // fallback and every path-derived capability reads unavailable —
    // exactly the /unavailable bounces observed during batch-restart
    // windows (marketplace checkout E2E landed on the disabled page).
    return this._loadCapabilitiesWithRetry(forceRefresh);
  }

  /**
   * Fetch the backend's path-derived capability manifest and build the
   * same CapabilitiesMap shape the OpenAPI derivation produces. Returns
   * null when the endpoint is unavailable (old backend) so callers fall
   * back to the OpenAPI path.
   */
  private async _loadManifestCapabilities(): Promise<CapabilitiesMap | null> {
    const MANIFEST_TIMEOUT_MS = 10_000;
    let response: { data: { capabilities?: Record<string, boolean> } };
    try {
      response = await apiClient
        .getClient()
        .get<{ capabilities?: Record<string, boolean> }>('/capabilities/manifest/', {
          timeout: MANIFEST_TIMEOUT_MS,
        });
    } catch {
      return null;
    }
    if (response.data?.capabilities == null) {
      return null;
    }
    const manifest = response.data.capabilities;
    // Same map shape as deriveCapabilitiesFromOpenAPI: name/endpoint from
    // the local definitions, availability from the server's precomputed
    // path presence (parity contract in hub/apps/api/capabilities.py).
    const capabilities: CapabilitiesMap = {};
    for (const def of CAPABILITY_DEFINITIONS) {
      capabilities[def.key] = {
        name: def.name,
        available: manifest[def.key] ?? false,
        endpoint: def.endpoint,
        ...(def.operationId ? { operationId: def.operationId } : {}),
      };
    }
    this.capabilities = capabilities;

    // Runtime overlay + snapshot identical to the OpenAPI path — a
    // manifest-derived session must answer the same for runtime keys
    // (asset_creation, data_quality*, compliance_*, databricks).
    try {
      await this.refreshRuntimeSnapshot();
    } catch {
      // Non-fatal, mirrors loadCapabilities' snapshot handling.
    }

    this.cachedAt = Date.now();
    return this.capabilities;
  }

  private _loadCapabilitiesRetried = false;

  private async _loadCapabilitiesWithRetry(forceRefresh: boolean): Promise<CapabilitiesMap> {
    // Check in-memory cache first (no localStorage — prevents client-side manipulation)
    if (!forceRefresh && this.cachedAt > 0 && Date.now() - this.cachedAt < CACHE_TTL) {
      return this.capabilities;
    }

    try {
      // 25s timeout: E2E/CI load (4 workers) can congest backend; retry handles transient failures
      const CAPABILITIES_TIMEOUT_MS = 25000;
      let response: { data: OpenAPISchema };
      try {
        response = await apiClient.getClient().get<OpenAPISchema>('/openapi.json', {
          timeout: CAPABILITIES_TIMEOUT_MS,
        });
      } catch (firstError) {
        // First OpenAPI fetch may fail under parallel E2E load or dev warm-up; we retry below.
        // Avoid console.error here — it pollutes browser logs during intentional retries (Vite dev
        // uses MODE=development; VITE_E2E_TEST is set by Playwright webServer).
        const isE2E = import.meta.env.VITE_E2E_TEST === 'true';
        if (import.meta.env.MODE !== 'test' && !isE2E) {
          console.warn('OpenAPI schema fetch failed (first attempt), retrying…', firstError);
        }
        // Retry once after delay (handles dev server warm-up and backend congestion)
        await new Promise((r) => setTimeout(r, 1500));
        response = await apiClient.getClient().get<OpenAPISchema>('/openapi.json', {
          timeout: CAPABILITIES_TIMEOUT_MS,
        });
      }

      this.openApiSchema = response.data;

      // Derive capabilities from OpenAPI paths
      this.capabilities = this.deriveCapabilitiesFromOpenAPI(this.openApiSchema);

      // Phase 250.6.D.2 — fetch runtime per-tenant capabilities so the
      // SPA can branch on ``asset_creation_blocked_reason``. Failure
      // here is non-fatal: the OpenAPI-derived caps are already
      // available, and a missing runtime snapshot just means the
      // SPA can't differentiate "incomplete onboarding" from
      // "ops-disabled" — the route-level CapabilityRoute still
      // redirects on the boolean flag in either case.
      try {
        await this.refreshRuntimeSnapshot();
      } catch {
        // Already logged inside refreshRuntimeSnapshot; nothing to do.
      }

      // Cache in-memory only when we have a valid schema (never cache empty on error)
      this.cachedAt = Date.now();

      return this.capabilities;
    } catch (error) {
      const isE2E = import.meta.env.VITE_E2E_TEST === 'true';
      if (import.meta.env.MODE !== 'test' && !isE2E) {
        console.error('Failed to load capabilities:', error);
      }
      // Do NOT cache empty capabilities so next load will retry.
      // Last-chance retry before falling back — see loadCapabilities.
      if (!this._loadCapabilitiesRetried) {
        this._loadCapabilitiesRetried = true;
        try {
          await new Promise((r) => setTimeout(r, 2000));
          return await this.loadCapabilities(true);
        } catch {
          /* fall through to the auth fallback below */
        }
      }
      // Fallback: assume auth endpoints available (backend has them; fail-open for registration/password-reset)
      this.capabilities = this.getAuthFallbackCapabilities();
      return this.capabilities;
    }
  }

  /**
   * Fallback capabilities when schema fetch fails. Assumes auth endpoints available (backend has them).
   */
  private getAuthFallbackCapabilities(): CapabilitiesMap {
    return {
      'auth.register': {
        name: 'User Registration',
        available: true,
        endpoint: '/api/v1/auth/register/',
        operationId: 'auth_register_create',
      },
      'auth.password-reset': {
        name: 'Password Reset Request',
        available: true,
        endpoint: '/api/v1/auth/password-reset/',
        operationId: 'auth_password_reset_create',
      },
      'auth.password-reset-confirm': {
        name: 'Password Reset Confirmation',
        available: true,
        endpoint: '/api/v1/auth/password-reset/confirm/',
        operationId: 'auth_password_reset_confirm_create',
      },
      // Phase 260.3.B — fail-open when OpenAPI fetch fails; backend still enforces kill-switch.
      datasets: {
        name: 'Datasets',
        available: true,
        endpoint: '/api/v1/datasets/',
      },
      files: {
        name: 'Files',
        available: true,
        endpoint: '/api/v1/files/',
      },
      // Phase 250.6.D — same fail-open contract for the asset-creation
      // kill switch. Without this key the fallback map answers
      // ``isCapabilityAvailable('asset_creation')`` with ``?? false`` and
      // ``<CapabilityRoute capability="asset_creation">`` bounces
      // /assets/create to /unavailable whenever the OpenAPI fetch hiccups
      // under load (E2E batch runs hit this repeatedly — the picker/form
      // testids never render). Mirrors ``refreshRuntimeSnapshot``'s
      // documented fail-open: the backend gate at POST /assets/ enforces
      // the real refusal, so a transient SPA-side fetch failure must not
      // hide the page. ``useFallbackCapabilities`` (the 30s load-timeout
      // path in useCapabilities) installs this same map, so both
      // failure modes stay consistent.
      asset_creation: {
        name: 'Asset Creation',
        available: true,
        endpoint: '/api/v1/assets/',
        operationId: 'asset_create',
      },
      // 313.H.4 — same fail-open contract for the marketplace subtree
      // (routes.tsx wraps /marketplace in CapabilityRoute "marketplace",
      // which derives from OpenAPI paths). Without this entry a transient
      // OpenAPI hiccup under batch load bounces EVERY marketplace route to
      // /unavailable (JOURNEY-MPA-002's PA landed there during stack
      // churn). Backend enforcement is unchanged: the marketplace API
      // gates on the per-tenant ``marketplace_integrations_enabled`` flag
      // server-side, so this is UX-grade only.
      marketplace: {
        name: 'Marketplace',
        available: true,
        endpoint: '/api/v1/marketplace/listings/',
      },
      // 313.H.4 — same fail-open contract for the marketplace-integrations
      // subtree (routes.tsx wraps /integrations in CapabilityRoute
      // "integrations.marketplace"). Absent here, a transient OpenAPI
      // hiccup under batch load bounces every /integrations route to
      // /unavailable (b6: the whole MP-001/003/004/006/007 cluster failed
      // on `expect(url).toContain(...)` with the URL at /unavailable).
      // Backend enforcement is unchanged: the integrations APIs gate on
      // the per-tenant paid-surface checks server-side (313.H.3), so this
      // is UX-grade only.
      'integrations.marketplace': {
        name: 'Marketplace Integrations',
        available: true,
        endpoint: '/api/v1/integrations/marketplace/connections/',
      },
      // close-test-coverage-gaps 1.2 — same fail-open contract for the
      // AI schema-matching route (routes.tsx wraps /ai/schema-matching in
      // CapabilityRoute capability="ai.schema-matching"). The backend
      // endpoint always exists (AIViewSet action — no tenant feature
      // flag), so a transient OpenAPI hiccup under batch load must not
      // bounce DE-008 to /unavailable before it reaches its real flow.
      // Backend enforcement is unchanged: this is UX-grade only.
      'ai.schema-matching': {
        name: 'AI Schema Matching',
        available: true,
        endpoint: '/api/v1/ai/schema-matching/',
      },
      // close-test-coverage-gaps 1.2 — same fail-open contract for the
      // developer subtree (routes.tsx wraps /developer in
      // CapabilityRoute capability="developer.plugins"). Absent here, a
      // transient capabilities hiccup bounces DE-012/DEV-009 to
      // /unavailable before the REAL gate runs — the backend 403
      // DEVELOPER_DISABLED on Tenant.developer_enabled=False is the
      // enforcement; this SPA-side entry is presentation-only.
      'developer.plugins': {
        name: 'Developer Plugins & Portal',
        available: true,
        endpoint: '/api/v1/developer/plugins/',
      },
      // Phase 228 F5/F3 — lineage runtime flags fail-open here too. The
      // time-travel controls / change-notifications UI gate on these
      // keys, and the gate is UX-only (the backend silently ignores the
      // anchor params when the flag is off) — so a transient
      // capabilities-load failure must not suppress the controls. This
      // was the exact state that timed out the lineage-time-travel E2E
      // under batch churn (b7): every load-failure path installed this
      // map WITHOUT lineage keys, fail-CLOSING the controls.
      'lineage.snapshots': {
        name: 'Lineage snapshots (point-in-time)',
        available: true,
        endpoint: '/api/v1/contracts/{id}/lineage/',
      },
      'lineage.change_notifications': {
        name: 'Lineage change notifications',
        available: true,
        endpoint: '/api/v1/contracts/{id}/lineage/subscriptions/',
      },
    };
  }

  /**
   * Derive capabilities from OpenAPI schema (data-driven — see
   * CAPABILITY_DEFINITIONS below; every key is enumerated there so the
   * paid-route drift test can assert route/nav keys stay registered).
   */
  private deriveCapabilitiesFromOpenAPI(schema: OpenAPISchema): CapabilitiesMap {
    return deriveCapabilitiesFromOpenAPI(schema);
  }

  /**
   * Phase 250.6.D.2 — fetch the per-tenant runtime capability response.
   *
   * Hits ``GET /api/v1/capabilities/`` (an AllowAny endpoint that
   * resolves the tenant from the session/JWT when present and
   * returns sensible anonymous defaults otherwise). Stores the
   * subset we care about today (``asset_creation`` +
   * ``asset_creation_blocked_reason``) in ``this.runtimeSnapshot``;
   * the OpenAPI-derived ``capabilities`` map remains the source of
   * truth for static-feature presence.
   *
   * Throws on network error so the caller (``loadCapabilities``)
   * can decide whether to retry; ``loadCapabilities`` swallows
   * the error because a missing runtime snapshot is a soft
   * degradation, not a fatal outage.
   */
  async refreshRuntimeSnapshot(): Promise<void> {
    const RUNTIME_TIMEOUT_MS = 10_000;
    type RuntimeResponse = {
      capabilities?: Partial<RuntimeCapabilitiesSnapshot>;
    };
    // ``apiClient.baseURL`` is already ``/api/v1`` (see
    // src/shared/api/client.ts:42) and ``InternalHttpClient._request``
    // builds ``${baseURL}/${url}`` — passing ``/api/v1/capabilities/``
    // here produces the path ``/api/v1/api/v1/capabilities/`` which
    // 404s. The runtime snapshot was therefore failing silently in
    // every run (the catch in ``loadCapabilities`` swallows the error),
    // and every ``CapabilityRoute`` that depends on a runtime-overlaid
    // key — ``asset_creation``, ``data_quality``, ``data_quality_advanced``,
    // ``datasets``, ``files``, the four compliance flags — fell through
    // to its default (mostly ``false``), which is exactly the
    // "feature unavailable" and "asset creation disabled" pages
    // observed across the entire E2E suite. Drop the ``/api/v1`` prefix
    // here; the client supplies it.
    try {
    const response = await apiClient
      .getClient()
      .get<RuntimeResponse>('/capabilities/', { timeout: RUNTIME_TIMEOUT_MS });
    const caps = response.data?.capabilities ?? {};
    // Defensive coercion: the backend can in theory return any shape;
    // we narrow to the documented contract here so the rest of the
    // SPA can rely on the type without runtime checks at every read.
    this.runtimeSnapshot = {
      asset_creation: caps.asset_creation === true,
      asset_creation_blocked_reason:
        caps.asset_creation_blocked_reason === 'ONBOARDING_INCOMPLETE' ||
        caps.asset_creation_blocked_reason === 'DISABLED_BY_OPS'
          ? caps.asset_creation_blocked_reason
          : null,
      datasets: caps.datasets !== false,
      files: caps.files !== false,
      // Phase 240.4.B.1 + B.4 — DQ kill switch + advanced gate. The
      // backend conjuncts ``data_quality_advanced = data_quality_enabled
      // AND data_quality_advanced_enabled`` on the wire, so we just
      // mirror the booleans here. ``data_quality`` is the only runtime
      // source for the base ``CapabilityRoute capability="data_quality"``
      // gate (the OpenAPI-derived map doesn't register this key —
      // adding the runtime read here closes the wiring gap that made
      // every DQ route resolve to the "feature unavailable" page even
      // when the tenant flag was True). ``!== false`` semantics: treat
      // an absent backend field as "available" so older API versions
      // without the field don't accidentally hide DQ.
      data_quality: caps.data_quality !== false,
      data_quality_advanced: caps.data_quality_advanced === true,
      compliance_consent: caps.compliance_consent === true,
      compliance_ropa: caps.compliance_ropa === true,
      compliance_dpia: caps.compliance_dpia === true,
      compliance_retention_enforcer: caps.compliance_retention_enforcer === true,
      // 313.H.4 — the breach + processor-agreements routes in routes.tsx
      // gated on these keys since Phase 232.3/232.6, but the snapshot
      // coercion never read them: both CapabilityRoutes silently
      // redirected every tenant to /unavailable. Backend keys:
      // compliance_breach_enabled / compliance_processor_agreements_enabled.
      compliance_dsar: caps.compliance_dsar === true,
      compliance_breach: caps.compliance_breach === true,
      compliance_processor_agreements: caps.compliance_processor_agreements === true,
      // openspec add-databricks-control-plane P0 — strict ``=== true``
      // (explicit opt-in, like the paid compliance keys). Absent key →
      // unavailable: the /databricks CapabilityRoute gate previously
      // resolved ``?? false`` for EVERY tenant because the backend
      // never sent the key and the overlay never registered it
      // (JOURNEY-DB-001 timed out waiting for the management page).
      databricks: caps.databricks === true,
      // Phase 228 F5/F3 — lineage settings-side flags. The backend emits
      // them on /api/v1/capabilities/ (LINEAGE_CAPABILITY_FLAGS, test
      // defaults TRUE) but the previous coercion whitelist dropped every
      // lineage.* key: lineage-time-travel controls never mounted in E2E
      // and the change-notifications subscription UI was silently hidden.
      'lineage.snapshots': caps['lineage.snapshots'] === true,
      'lineage.change_notifications': caps['lineage.change_notifications'] === true,
      // Phase 278.R.6 (close-test-coverage-gaps 3.2) — strict ``=== true``
      // (explicit opt-in, like the paid compliance keys): a backend that
      // doesn't emit ux_v2 leaves the tour hidden, never guessing.
      ux_v2: caps.ux_v2 === true,
    };
    } catch (err) {
      // Fail-OPEN for the kill switch when the snapshot cannot be fetched:
      // the overlay below must still run (with the fail-open default) so a
      // transient capabilities-endpoint hiccup does NOT bounce users to
      // /unavailable — the backend gate at POST /assets/ enforces the real
      // refusal regardless (documented contract in
      // ``isAssetCreationAllowedRuntime``). This was the intermittent
      // "Capability key: asset_creation" page observed across the E2E
      // suite under batch load.
      this.runtimeSnapshot = null;
      this.applyRuntimeOverlay();
      throw err;
    }
    this.applyRuntimeOverlay();
  }

  /**
   * Register the runtime snapshot values onto the derived capabilities map.
   * Runs in BOTH snapshot outcomes (success and the fail-open null path) so
   * route-level CapabilityRoute gates always read a live value or the
   * documented fail-open default — never the ``?? false`` fallback.
   * Null-safe: every read uses ``?.``; absent backend fields keep the
   * ``refreshRuntimeSnapshot`` semantics (available for asset_creation /
   * datasets / files / data_quality; strict ``=== true`` for the
   * advanced/paid keys).
   */
  private applyRuntimeOverlay(): void {
    // Phase 250.6.D / 250.6.A wiring closeout — register the runtime
    // ``asset_creation`` flag in ``this.capabilities`` so the
    // existing ``<CapabilityRoute capability="asset_creation">``
    // gate at /assets/create reads the LIVE per-tenant value
    // instead of falling through to the ``?? false`` default
    // (which was the original 250.6.A wiring gap — the OpenAPI
    // schema doesn't expose ``asset_creation`` as a path-derived
    // capability, so the key never appeared in the map and every
    // user got redirected to /unavailable).
    //
    // For the ``ONBOARDING_INCOMPLETE`` case we DELIBERATELY
    // register ``available: true`` so the route stays reachable —
    // the page itself reads ``getAssetCreationBlockedReason()`` and
    // renders the onboarding-CTA picker variant. For
    // ``DISABLED_BY_OPS`` we keep ``available: false`` so the
    // CapabilityRoute redirect (the existing 250.6.A behavior)
    // fires and the user lands on the generic disabled page.
    const reason = this.runtimeSnapshot?.asset_creation_blocked_reason ?? null;
    const routeAvailable =
      (this.runtimeSnapshot?.asset_creation ?? true) ||
      reason === 'ONBOARDING_INCOMPLETE';
    this.capabilities['asset_creation'] = {
      name: 'Asset Creation',
      available: routeAvailable,
      endpoint: '/api/v1/assets/',
      operationId: 'asset_create',
    };

    this.capabilities['datasets'] = {
      name: 'Datasets',
      available: this.runtimeSnapshot?.datasets !== false,
      endpoint: '/api/v1/datasets/',
    };

    this.capabilities['files'] = {
      name: 'Files',
      available: this.runtimeSnapshot?.files !== false,
      endpoint: '/api/v1/files/',
    };

    // Phase 240.4.B.1 + 240.4.B.4 wiring closeout — register the runtime
    // DQ flags so the route guards at routes.tsx:1171
    // (``capability="data_quality"``) and 1195/1203/1211/1219/1227
    // (``capability="data_quality_advanced"``) read the LIVE per-tenant
    // value. Without these registrations, the OpenAPI-derived map
    // never sees these keys and ``isCapabilityAvailable`` returns false
    // for every tenant — the wire response was correct, the SPA just
    // didn't read it. Mirrors the ``asset_creation`` wiring above.
    this.capabilities['data_quality'] = {
      name: 'Data Quality',
      available: this.runtimeSnapshot?.data_quality !== false,
      endpoint: '/api/v1/dq/',
    };
    this.capabilities['data_quality_advanced'] = {
      name: 'Data Quality (advanced)',
      available: this.runtimeSnapshot?.data_quality_advanced === true,
      endpoint: '/api/v1/dq/',
    };

    // Phase 228 F5/F3 — lineage runtime flags: register onto the derived
    // map so isCapabilityAvailable('lineage.snapshots' |
    // 'lineage.change_notifications') reads the live settings-side value
    // (the manifest is path-derived and never carries these keys).
    // FAIL-OPEN when the snapshot does not carry the key (snapshot fetch
    // failed → runtimeSnapshot is null, or an older backend that never
    // emits it): the gates are UX-only — the backend silently ignores
    // the anchor params when the flag is off — so a transient
    // capabilities hiccup must not suppress the time-travel controls
    // (the b7 lineage-time-travel E2E timed out in exactly this state).
    // Only an EXPLICIT ``false`` on the wire hides them.
    this.capabilities['lineage.snapshots'] = {
      name: 'Lineage snapshots (point-in-time)',
      available:
        this.runtimeSnapshot == null ||
        this.runtimeSnapshot['lineage.snapshots'] !== false,
      endpoint: '/api/v1/contracts/{id}/lineage/',
    };
    this.capabilities['lineage.change_notifications'] = {
      name: 'Lineage change notifications',
      available:
        this.runtimeSnapshot == null ||
        this.runtimeSnapshot['lineage.change_notifications'] !== false,
      endpoint: '/api/v1/contracts/{id}/lineage/subscriptions/',
    };

    this.capabilities['compliance_consent'] = {
      name: 'Compliance consent',
      available: this.runtimeSnapshot?.compliance_consent === true,
      endpoint: '/api/v1/consent/consent-records/',
    };

    this.capabilities['compliance_ropa'] = {
      name: 'Compliance RoPA',
      available: this.runtimeSnapshot?.compliance_ropa === true,
      endpoint: '/api/v1/ropa/generations/',
    };

    this.capabilities['compliance_dpia'] = {
      name: 'Compliance DPIA',
      available: this.runtimeSnapshot?.compliance_dpia === true,
      endpoint: '/api/v1/dpia/records/',
    };

    this.capabilities['compliance_retention_enforcer'] = {
      name: 'Retention auto-enforcement',
      available: this.runtimeSnapshot?.compliance_retention_enforcer === true,
      endpoint: '/api/v1/governance/retention-policies/dashboard/',
    };

    // 313.H.4 review — register the dsar/breach/processor runtime flags
    // (the routes.tsx CapabilityRoutes read them; see the snapshot
    // coercion note above).
    this.capabilities['compliance_dsar'] = {
      name: 'Compliance DSAR handler queue',
      available: this.runtimeSnapshot?.compliance_dsar === true,
      endpoint: '/api/v1/dsar/requests/',
    };

    this.capabilities['compliance_breach'] = {
      name: 'Compliance breach register',
      available: this.runtimeSnapshot?.compliance_breach === true,
      endpoint: '/api/v1/breach/incidents/',
    };

    this.capabilities['compliance_processor_agreements'] = {
      name: 'Processor agreements register',
      available: this.runtimeSnapshot?.compliance_processor_agreements === true,
      endpoint: '/api/v1/processor-agreements/processors/',
    };

    // openspec add-databricks-control-plane P0 — the /databricks route
    // gates on this key. Strict (=== true): a missing snapshot field or
    // a fail-open null snapshot leaves the paid control-plane surface
    // unavailable rather than guessing. Mirrors the compliance keys.
    this.capabilities['databricks'] = {
      name: 'Databricks Control Plane',
      available: this.runtimeSnapshot?.databricks === true,
      endpoint: '/api/v1/databricks/',
    };

    // Phase 278.R.6 (close-test-coverage-gaps 3.2) — UX v2 staged
    // rollout. Strict (=== true), same fail-closed shape as the paid
    // keys above: an absent/failed snapshot hides the product tour
    // rather than popping an overlay on tenants that opted out.
    this.capabilities['ux_v2'] = {
      name: 'UX v2',
      available: this.runtimeSnapshot?.ux_v2 === true,
      endpoint: '/api/v1/capabilities/',
    };
  }

  /**
   * Phase 250.6.D.2 — read the asset-creation block reason from the
   * cached runtime snapshot. Returns ``null`` if no snapshot has
   * been loaded yet OR if the gate is currently open. Callers (e.g.
   * the AssetTypePickerStep) MUST handle ``null`` as "do not show
   * the onboarding CTA" — same as "fully unblocked".
   */
  getAssetCreationBlockedReason(): AssetCreationBlockedReason {
    return this.runtimeSnapshot?.asset_creation_blocked_reason ?? null;
  }

  /**
   * Phase 250.6.D.2 — read the asset-creation boolean from the
   * runtime snapshot. Returns ``true`` (open) when no snapshot
   * has loaded — fail-open is the right default for the kill
   * switch (the backend gate at ``POST /assets/`` enforces the
   * real refusal regardless).
   */
  isAssetCreationAllowedRuntime(): boolean {
    return this.runtimeSnapshot?.asset_creation ?? true;
  }

  /**
   * Force use of auth fallback capabilities (e.g. when load times out).
   * Ensures auth routes (register, password-reset) remain accessible.
   */
  useFallbackCapabilities(): void {
    this.capabilities = this.getAuthFallbackCapabilities();
  }

  /**
   * Check if a capability is available
   */
  isCapabilityAvailable(capabilityKey: string): boolean {
    const capability = this.capabilities[capabilityKey];
    return capability?.available ?? false;
  }

  /**
   * Get capability details
   */
  getCapability(capabilityKey: string): Capability | null {
    return this.capabilities[capabilityKey] || null;
  }

  /**
   * Get all capabilities
   */
  getAllCapabilities(): CapabilitiesMap {
    return { ...this.capabilities };
  }

  /**
   * Runtime probe (optional, for non-prod environments)
   */
  async probeCapability(endpoint: string): Promise<boolean> {
    if (import.meta.env.PROD) {
      // Don't probe in production
      return this.isCapabilityAvailable(endpoint);
    }

    try {
      // Try a HEAD or OPTIONS request
      await apiClient.getClient().head(endpoint);
      return true;
    } catch {
      return false;
    }
  }
}

export const capabilitiesService = new CapabilitiesService();
