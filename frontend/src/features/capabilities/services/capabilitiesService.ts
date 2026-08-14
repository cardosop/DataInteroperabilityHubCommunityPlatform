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

class CapabilitiesService {
  private capabilities: CapabilitiesMap = {};
  private openApiSchema: OpenAPISchema | null = null;
  private cachedAt = 0;
  // Phase 250.6.D.2 — runtime capabilities snapshot (per-tenant).
  // Fetched alongside the OpenAPI schema; null until first fetch.
  private runtimeSnapshot: RuntimeCapabilitiesSnapshot | null = null;

  /**
   * Load OpenAPI schema and derive capabilities
   */
  async loadCapabilities(forceRefresh = false): Promise<CapabilitiesMap> {
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
    };
  }

  /**
   * Derive capabilities from OpenAPI schema
   */
  private deriveCapabilitiesFromOpenAPI(schema: OpenAPISchema): CapabilitiesMap {
    const capabilities: CapabilitiesMap = {};
    const paths = schema.paths || {};

    // Auth capabilities (Visitor persona)
    // Support both /api/v1/auth/... and /auth/... path formats (drf-spectacular may vary)
    const authRegisterAvailable =
      '/api/v1/auth/register/' in paths ||
      Object.keys(paths).some((p) => p.includes('auth/register') || p.endsWith('auth/register/'));
    capabilities['auth.register'] = {
      name: 'User Registration',
      available: authRegisterAvailable,
      endpoint: '/api/v1/auth/register/',
      operationId: 'auth_register_create',
    };

    const authPasswordResetAvailable =
      '/api/v1/auth/password-reset/' in paths ||
      Object.keys(paths).some((p) => p.includes('auth/password-reset') && !p.includes('confirm'));
    capabilities['auth.password-reset'] = {
      name: 'Password Reset Request',
      available: authPasswordResetAvailable,
      endpoint: '/api/v1/auth/password-reset/',
      operationId: 'auth_password_reset_create',
    };

    const authPasswordResetConfirmAvailable =
      '/api/v1/auth/password-reset/confirm/' in paths ||
      Object.keys(paths).some((p) => p.includes('auth/password-reset') && p.includes('confirm'));
    capabilities['auth.password-reset-confirm'] = {
      name: 'Password Reset Confirmation',
      available: authPasswordResetConfirmAvailable,
      endpoint: '/api/v1/auth/password-reset/confirm/',
      operationId: 'auth_password_reset_confirm_create',
    };

    // AI capabilities
    capabilities['ai.natural-language-search'] = {
      name: 'AI Natural Language Search',
      available: '/api/v1/ai/natural-language-search/' in paths,
      endpoint: '/api/v1/ai/natural-language-search/',
      operationId: 'natural_language_search',
    };

    capabilities['ai.schema-matching'] = {
      name: 'AI Schema Matching',
      available: '/api/v1/ai/schema-matching/' in paths,
      endpoint: '/api/v1/ai/schema-matching/',
      operationId: 'schema_matching',
    };

    // Search (full-text) — Phase 273.1 canonical endpoint
    const searchPathAvailable =
      '/api/search/' in paths ||
      Object.keys(paths).some((p) => p === '/api/search/');
    capabilities['search.full-text'] = {
      name: 'Full-Text Search',
      available: searchPathAvailable,
      endpoint: '/api/search/',
      operationId: 'unified_search',
    };

    // Semantic capabilities
    const semanticSparqlAvailable =
      '/api/v1/semantic/sparql' in paths ||
      Object.keys(paths).some((p) => p.includes('semantic/sparql'));
    capabilities['semantic.sparql'] = {
      name: 'Semantic SPARQL',
      available: semanticSparqlAvailable,
      endpoint: '/api/v1/semantic/sparql',
      operationId: 'sparql_query',
    };

    capabilities['ai.classification'] = {
      name: 'AI Classification',
      available: '/api/v1/ai/classification/' in paths,
      endpoint: '/api/v1/ai/classification/',
    };

    capabilities['ai.recommendations'] = {
      name: 'AI Recommendations',
      available: '/api/v1/ai/recommendations/' in paths,
      endpoint: '/api/v1/ai/recommendations/',
    };

    capabilities['ai.anomaly-detection'] = {
      name: 'AI Anomaly Detection',
      available: '/api/v1/ai/anomaly-detection/' in paths,
      endpoint: '/api/v1/ai/anomaly-detection/',
    };

    // Phase 228.F1 (REQ-LIN-F1-004) — Cross-tenant marketplace lineage.
    // Detected via the OpenAPI path for the per-listing lineage action.
    // drf-spectacular emits the path with the listing id placeholder
    // (`{id}` or `{listing_id}` depending on the lookup field), so we
    // accept any path matching `/marketplace/listings/{*}/lineage/`.
    const lineageMarketplaceAvailable = Object.keys(paths).some(
      (p) => /\/marketplace\/listings\/\{[^}]+\}\/lineage\/?$/.test(p),
    );
    capabilities['lineage.cross_tenant_marketplace'] = {
      name: 'Cross-Tenant Marketplace Lineage',
      available: lineageMarketplaceAvailable,
      endpoint: '/api/v1/marketplace/listings/{id}/lineage/',
      operationId: 'listing_lineage',
    };

    // Phase 228.F2.32 — Field-level lineage editor.  Detected via the
    // PATCH method on the per-contract lineage path; drf-spectacular
    // emits the path with the lookup placeholder (`{id}`) and the
    // operation key includes `patch` when the action is registered.
    const lineageFieldEditorAvailable = Object.keys(paths).some((p) => {
      if (!/\/contracts\/\{[^}]+\}\/lineage\/?$/.test(p)) return false;
      const ops = paths[p];
      return Boolean(ops && typeof ops === 'object' && 'patch' in (ops as object));
    });
    capabilities['contracts.lineage_field_editor'] = {
      name: 'Field-Level Lineage Editor',
      available: lineageFieldEditorAvailable,
      endpoint: '/api/v1/contracts/{id}/lineage/',
      operationId: 'contract_lineage_edit',
    };

    // Social capabilities
    capabilities['social.ratings'] = {
      name: 'Social Ratings',
      available: '/api/v1/social/ratings/' in paths,
      endpoint: '/api/v1/social/ratings/',
    };

    capabilities['social.reviews'] = {
      name: 'Social Reviews',
      available: '/api/v1/social/reviews/' in paths,
      endpoint: '/api/v1/social/reviews/',
    };

    capabilities['social.comments'] = {
      name: 'Social Comments',
      available: '/api/v1/social/comments/' in paths,
      endpoint: '/api/v1/social/comments/',
    };

    capabilities['social.communities'] = {
      name: 'Social Communities',
      available: '/api/v1/social/communities/' in paths,
      endpoint: '/api/v1/social/communities/',
    };

    capabilities['social.activity-feeds'] = {
      name: 'Social Activity Feeds',
      available: Object.keys(paths).some(
        (path) => path.includes('/social/') && path.includes('/feed')
      ),
      endpoint: '/api/v1/social/feed/',
    };

    // Developer Portal capabilities
    capabilities['developer.plugins'] = {
      name: 'Developer Plugins',
      available: '/api/v1/developer/plugins/' in paths,
      endpoint: '/api/v1/developer/plugins/',
    };

    capabilities['developer.sdk'] = {
      name: 'Developer SDK Documentation',
      available: '/api/v1/developer/sdk/' in paths,
      endpoint: '/api/v1/developer/sdk/',
    };

    // BaaS capabilities
    capabilities['baas.api-keys'] = {
      name: 'BaaS API Keys',
      available: '/api/v1/baas/api-keys/' in paths,
      endpoint: '/api/v1/baas/api-keys/',
    };

    capabilities['baas.usage'] = {
      name: 'BaaS Usage Tracking',
      available: '/api/v1/baas/usage/' in paths,
      endpoint: '/api/v1/baas/usage/',
    };

    // ML/ODH capabilities
    capabilities['ml.models'] = {
      name: 'ML Models',
      available: '/api/v1/ml/models/' in paths,
      endpoint: '/api/v1/ml/models/',
    };

    capabilities['ml.training'] = {
      name: 'ML Training Jobs',
      available: '/api/v1/ml/training/jobs/' in paths,
      endpoint: '/api/v1/ml/training/jobs/',
    };

    capabilities['ml.inference'] = {
      name: 'ML Inference Deployments',
      available: '/api/v1/ml/inference/deployments/' in paths,
      endpoint: '/api/v1/ml/inference/deployments/',
    };

    // Transformation pipelines (placeholder API exists at /api/v1/transformation/pipelines/)
    const transformationAvailable =
      '/api/v1/transformation/pipelines/' in paths ||
      Object.keys(paths).some((p) => p.includes('transformation/pipelines') || p.includes('transformation.pipelines'));
    capabilities['transformation'] = {
      name: 'Transformation',
      available: transformationAvailable,
      endpoint: '/api/v1/transformation/pipelines/',
    };
    capabilities['transformation.pipelines'] = {
      name: 'Transformation Pipelines',
      available: transformationAvailable,
      endpoint: '/api/v1/transformation/pipelines/',
    };

    const meshDomainsAvailable =
      '/api/v1/mesh/domains/' in paths ||
      Object.keys(paths).some((p) => p.includes('/mesh/domains'));
    capabilities['mesh.domains'] = {
      name: 'Data Mesh Domains',
      available: meshDomainsAvailable,
      endpoint: '/api/v1/mesh/domains/',
    };

    const virtualizationDatasetsAvailable =
      '/api/v1/virtualization/datasets/' in paths ||
      Object.keys(paths).some((p) => p.includes('/virtualization/datasets'));
    capabilities['virtualization.datasets'] = {
      name: 'Virtualization Datasets',
      available: virtualizationDatasetsAvailable,
      endpoint: '/api/v1/virtualization/datasets/',
    };

    const integrationsMarketplaceAvailable =
      '/api/v1/integrations/marketplace/connections/' in paths ||
      Object.keys(paths).some(
        (p) => p.includes('/integrations/') && p.includes('marketplace'),
      );
    capabilities['integrations.marketplace'] = {
      name: 'Marketplace Integrations',
      available: integrationsMarketplaceAvailable,
      endpoint: '/api/v1/integrations/marketplace/connections/',
    };

    const retentionAutosweepEndpoints = Object.keys(paths).some(
      (p) =>
        p.includes('/governance/retention-policies') &&
        (p.includes('/dashboard') || p.includes('dashboard')),
    );
    capabilities['compliance_retention_enforcer'] = {
      name: 'Retention auto-enforcement',
      available: retentionAutosweepEndpoints,
      endpoint: '/api/v1/governance/retention-policies/dashboard/',
    };

    // Phase 260.3.B — Hub datasets/files REST (not virtualization.datasets).
    // OpenAPI presence ⇒ route reachable; refreshRuntimeSnapshot overlays tenant kill-switch.
    const hubDatasetsApiAvailable =
      '/api/v1/datasets/' in paths ||
      Object.keys(paths).some(
        (p) =>
          /\/api\/v1\/datasets\//.test(p) && !p.toLowerCase().includes('/virtualization/'),
      );
    capabilities['datasets'] = {
      name: 'Datasets',
      available: hubDatasetsApiAvailable,
      endpoint: '/api/v1/datasets/',
    };

    const hubFilesApiAvailable =
      '/api/v1/files/' in paths ||
      Object.keys(paths).some((p) => /\/api\/v1\/files\//.test(p));
    capabilities['files'] = {
      name: 'Files',
      available: hubFilesApiAvailable,
      endpoint: '/api/v1/files/',
    };

    return capabilities;
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
    const response = await apiClient.getClient().get<RuntimeResponse>(
      '/capabilities/',
      { timeout: RUNTIME_TIMEOUT_MS },
    );
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
      plan_compliance_pro_pack: caps.plan_compliance_pro_pack === true,
    };

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
    const reason = this.runtimeSnapshot.asset_creation_blocked_reason;
    const routeAvailable =
      this.runtimeSnapshot.asset_creation || reason === 'ONBOARDING_INCOMPLETE';
    this.capabilities['asset_creation'] = {
      name: 'Asset Creation',
      available: routeAvailable,
      endpoint: '/api/v1/assets/',
      operationId: 'asset_create',
    };

    this.capabilities['datasets'] = {
      name: 'Datasets',
      available: this.runtimeSnapshot.datasets !== false,
      endpoint: '/api/v1/datasets/',
    };

    this.capabilities['files'] = {
      name: 'Files',
      available: this.runtimeSnapshot.files !== false,
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
      available: this.runtimeSnapshot.data_quality !== false,
      endpoint: '/api/v1/dq/',
    };
    this.capabilities['data_quality_advanced'] = {
      name: 'Data Quality (advanced)',
      available: this.runtimeSnapshot.data_quality_advanced === true,
      endpoint: '/api/v1/dq/',
    };

    this.capabilities['compliance_consent'] = {
      name: 'Compliance consent',
      available: this.runtimeSnapshot.compliance_consent === true,
      endpoint: '/api/v1/governance/consent-records/',
    };

    this.capabilities['compliance_ropa'] = {
      name: 'Compliance RoPA',
      available: this.runtimeSnapshot.compliance_ropa === true,
      endpoint: '/api/v1/ropa/generations/',
    };

    this.capabilities['compliance_dpia'] = {
      name: 'Compliance DPIA',
      available: this.runtimeSnapshot.compliance_dpia === true,
      endpoint: '/api/v1/dpia/records/',
    };

    this.capabilities['compliance_retention_enforcer'] = {
      name: 'Retention auto-enforcement',
      available: this.runtimeSnapshot.compliance_retention_enforcer === true,
      endpoint: '/api/v1/governance/retention-policies/dashboard/',
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
