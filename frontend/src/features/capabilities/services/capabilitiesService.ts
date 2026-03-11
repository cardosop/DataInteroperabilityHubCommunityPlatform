/**
 * Capabilities Service
 * Derives capabilities from OpenAPI presence and optional runtime probe
 */

import { apiClient } from '../../../shared/api/client';
import type {
  CapabilitiesMap,
  Capability,
  OpenAPISchema,
} from '../../../shared/types/capabilities';

const CAPABILITIES_CACHE_KEY = 'capabilities_cache';
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

interface CachedCapabilities {
  capabilities: CapabilitiesMap;
  timestamp: number;
}

class CapabilitiesService {
  private capabilities: CapabilitiesMap = {};
  private openApiSchema: OpenAPISchema | null = null;

  /**
   * Load OpenAPI schema and derive capabilities
   */
  async loadCapabilities(forceRefresh = false): Promise<CapabilitiesMap> {
    // Check cache first
    if (!forceRefresh) {
      const cached = this.getCachedCapabilities();
      if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
        this.capabilities = cached.capabilities;
        return this.capabilities;
      }
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
        if (import.meta.env.MODE !== 'test') {
          console.error('Failed to load capabilities (first attempt):', firstError);
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

      // Cache capabilities only when we have a valid schema (never cache empty on error)
      this.cacheCapabilities(this.capabilities);

      return this.capabilities;
    } catch (error) {
      if (import.meta.env.MODE !== 'test') {
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

    // Search (full-text)
    const searchPathAvailable =
      '/api/v1/search/search/' in paths ||
      Object.keys(paths).some((p) => p.includes('search/search'));
    capabilities['search.full-text'] = {
      name: 'Full-Text Search',
      available: searchPathAvailable,
      endpoint: '/api/v1/search/search/',
      operationId: 'search_search',
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
      Object.keys(paths).some((p) => p.includes('transformation/pipelines'));
    capabilities['transformation'] = {
      name: 'Transformation',
      available: transformationAvailable,
      endpoint: '/api/v1/transformation/pipelines/',
    };

    return capabilities;
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
    } catch (error) {
      return false;
    }
  }

  private getCachedCapabilities(): CachedCapabilities | null {
    try {
      const cached = localStorage.getItem(CAPABILITIES_CACHE_KEY);
      if (!cached) return null;
      return JSON.parse(cached) as CachedCapabilities;
    } catch {
      return null;
    }
  }

  private cacheCapabilities(capabilities: CapabilitiesMap): void {
    try {
      const cached: CachedCapabilities = {
        capabilities,
        timestamp: Date.now(),
      };
      localStorage.setItem(CAPABILITIES_CACHE_KEY, JSON.stringify(cached));
    } catch (error) {
      console.warn('Failed to cache capabilities:', error);
    }
  }
}

export const capabilitiesService = new CapabilitiesService();
