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
      // Fetch OpenAPI schema
      const response = await apiClient.getClient().get<OpenAPISchema>('/openapi.json');
      this.openApiSchema = response.data;

      // Derive capabilities from OpenAPI paths
      this.capabilities = this.deriveCapabilitiesFromOpenAPI(this.openApiSchema);

      // Cache capabilities
      this.cacheCapabilities(this.capabilities);

      return this.capabilities;
    } catch (error) {
      console.error('Failed to load capabilities:', error);
      // Return empty capabilities on error
      return {};
    }
  }

  /**
   * Derive capabilities from OpenAPI schema
   */
  private deriveCapabilitiesFromOpenAPI(schema: OpenAPISchema): CapabilitiesMap {
    const capabilities: CapabilitiesMap = {};
    const paths = schema.paths || {};

    // Auth capabilities (Visitor persona)
    capabilities['auth.register'] = {
      name: 'User Registration',
      available: '/api/v1/auth/register/' in paths,
      endpoint: '/api/v1/auth/register/',
      operationId: 'auth_register_create',
    };

    capabilities['auth.password-reset'] = {
      name: 'Password Reset Request',
      available: '/api/v1/auth/password-reset/' in paths,
      endpoint: '/api/v1/auth/password-reset/',
      operationId: 'auth_password_reset_create',
    };

    capabilities['auth.password-reset-confirm'] = {
      name: 'Password Reset Confirmation',
      available: '/api/v1/auth/password-reset/confirm/' in paths,
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

    // Transformation (should be Red - removed)
    capabilities['transformation'] = {
      name: 'Transformation',
      available: false, // Explicitly false - feature removed
    };

    return capabilities;
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
