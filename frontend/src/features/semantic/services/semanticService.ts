/**
 * Semantic Service
 * API client for semantic operations (SPARQL, URI resolution, ontology, JSON-LD context)
 */

import { apiClient } from '../../../shared/api/client';
import type {
  SemanticResourceListFilters,
  SemanticResourceListResponse,
  SPARQLQueryRequest,
  SPARQLQueryResponse,
  URIResolutionResponse,
} from '../../../shared/types/semantic';

const SEMANTIC_BASE_PATH = 'semantic';

export const semanticService = {
  /**
   * Execute SPARQL query (POST)
   */
  async querySPARQL(data: SPARQLQueryRequest): Promise<SPARQLQueryResponse> {
    const response = await apiClient
      .getClient()
      .post<SPARQLQueryResponse>(`${SEMANTIC_BASE_PATH}/sparql`, data);
    return response.data;
  },

  /**
   * Execute SPARQL query via GET (for simple queries)
   */
  async querySPARQLGet(
    query: string,
    format: SPARQLQueryRequest['format'] = 'json'
  ): Promise<SPARQLQueryResponse> {
    const params = new URLSearchParams();
    params.set('query', query);
    if (format) params.set('format', format);
    const response = await apiClient
      .getClient()
      .get<SPARQLQueryResponse>(`${SEMANTIC_BASE_PATH}/sparql?${params.toString()}`);
    return response.data;
  },

  /**
   * Resolve URI to JSON-LD
   */
  async resolveURI(resourceType: string, resourceId: string): Promise<URIResolutionResponse> {
    const response = await apiClient
      .getClient()
      .get<URIResolutionResponse>(`${SEMANTIC_BASE_PATH}/id/${resourceType}/${resourceId}`);
    return response.data;
  },

  /**
   * Resolve field URI to JSON-LD
   */
  async resolveFieldURI(assetUuid: string, fieldName: string): Promise<URIResolutionResponse> {
    const response = await apiClient
      .getClient()
      .get<URIResolutionResponse>(`${SEMANTIC_BASE_PATH}/id/field/${assetUuid}/${fieldName}`);
    return response.data;
  },

  /**
   * Get ontology definition (Turtle format)
   */
  async getOntology(): Promise<string> {
    const response = await apiClient.getClient().get<string>(`${SEMANTIC_BASE_PATH}/ontology`, {
      responseType: 'text',
      headers: {
        Accept: 'text/turtle, text/plain, */*',
      },
    });
    return response.data;
  },

  /**
   * Get JSON-LD context
   */
  async getJSONLDContext(): Promise<Record<string, unknown>> {
    const response = await apiClient
      .getClient()
      .get<Record<string, unknown>>(`${SEMANTIC_BASE_PATH}/context.jsonld`);
    return response.data;
  },

  /**
   * List semantic resources (tenant-scoped)
   */
  async listResources(
    filters: SemanticResourceListFilters = {}
  ): Promise<SemanticResourceListResponse> {
    const params = new URLSearchParams();
    if (filters.page != null) params.set('page', String(filters.page));
    if (filters.page_size != null) params.set('page_size', String(filters.page_size));
    const qs = params.toString();
    const url = qs
      ? `${SEMANTIC_BASE_PATH}/semantic-resources/?${qs}`
      : `${SEMANTIC_BASE_PATH}/semantic-resources/`;
    const response = await apiClient.getClient().get<SemanticResourceListResponse>(url);
    return response.data;
  },
};
