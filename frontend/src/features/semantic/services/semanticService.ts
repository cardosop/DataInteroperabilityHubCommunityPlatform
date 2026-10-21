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
   * Phase 230.2.9 (REQ-SEM-EXPORT-001) — bulk RDF export.
   *
   * POST /api/v1/semantic/export — returns the tenant's full graph
   * in the requested serialization. Body is the binary RDF (a Blob);
   * caller is responsible for triggering the browser download
   * (typically `URL.createObjectURL(blob)` + `<a download>` click).
   *
   * The 4 supported formats map to MIME types:
   *   - n-triples → application/n-triples
   *   - turtle    → text/turtle
   *   - rdf-xml   → application/rdf+xml
   *   - ld+json   → application/ld+json
   *
   * Server-side throttle: 5 requests / 5 minutes / user.
   * Server-side cap: 100M triples → HTTP 413 (caller surfaces a
   * "use SPARQL pagination" hint in the UI).
   */
  async exportRdf(
    format: 'n-triples' | 'turtle' | 'rdf-xml' | 'ld+json' = 'n-triples',
  ): Promise<Blob> {
    const response = await apiClient
      .getClient()
      .post(`${SEMANTIC_BASE_PATH}/export`, { format }, {
        responseType: 'blob',
      });
    return response.data as Blob;
  },

  /**
   * Phase 230.5.5 (REQ-SEM-RELATIONSHIPS-001) — fetch RDF
   * relationships for a contract.
   *
   * GET /api/v1/semantic/relationships/{contract_id}
   *
   * Returns ``{triples, status}`` where ``triples`` is the
   * N-Triples text and ``status`` is ``OK`` or ``DEGRADED``.
   * The Django route is tenant-scoped — a cross-tenant contract
   * id returns 404, so the caller can rely on the response either
   * being for a contract the user can see, or a 404.
   */
  async getContractRelationships(
    contractId: string,
  ): Promise<{ triples: string; status: 'OK' | 'DEGRADED' }> {
    const response = await apiClient
      .getClient()
      .get<{ triples: string; status: 'OK' | 'DEGRADED' }>(
        `${SEMANTIC_BASE_PATH}/relationships/${contractId}`,
      );
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
