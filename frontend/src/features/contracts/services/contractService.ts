/**
 * Contract Service
 * API client for contract operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  Contract,
  ContractCreateRequest,
  ContractUpdateRequest,
  ContractListFilters,
  ContractValidationResult,
  ContractLintResult,
  ContractConvertRequest,
  ContractConvertResult,
  DraftValidationResult,
} from '../../../shared/types/contracts';
import type {
  ContractLineageVisualization,
  ContractLineageVisualizationParams,
} from '../../../shared/types/lineage';
import type {
  ODPSProductCreateRequest,
  ODPSProductCreateResponse,
  ODPSWorkflowStatus,
  ODPSLinkRequest,
  ODPSLinkResponse,
  ODPSLinks,
  ODPSExportParams,
} from '../../../shared/types/odps';

const CONTRACTS_BASE_PATH = 'contracts';

export const contractService = {
  /**
   * List contracts with filtering and pagination
   */
  async list(filters: ContractListFilters = {}): Promise<PaginatedResponse<Contract>> {
    const params = new URLSearchParams();
    
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.search) params.append('search', filters.search);
    if (filters.owner_email) params.append('owner_email', filters.owner_email);
    if (filters.owner_name) params.append('owner_name', filters.owner_name);
    if (filters.tag) params.append('tag', filters.tag);
    if (filters.quality_profile) params.append('quality_profile', filters.quality_profile);
    if (filters.compliance_regime) params.append('compliance_regime', filters.compliance_regime);
    if (filters.asset_id) params.append('asset_id', filters.asset_id);
    if (filters.spec_type) params.append('spec_type', filters.spec_type);
    if (filters.filter) params.append('filter', filters.filter);

    const response = await apiClient.getClient().get<PaginatedResponse<Contract>>(
      `${CONTRACTS_BASE_PATH}/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Get contract by ID.
   *
   * Phase 227 Wave 1 (227.L5.6) — captures the ``ETag`` response header
   * (RFC 7232 weak validator) and surfaces it on the returned object as
   * ``etag``. The Schema editor stores this and sends it back as
   * ``If-Match`` on PATCH for optimistic-concurrency control.
   */
  async getById(id: string): Promise<Contract & { etag?: string | null }> {
    const response = await apiClient
      .getClient()
      .get<Contract>(`${CONTRACTS_BASE_PATH}/${id}/`);
    const etag =
      (response.headers as Record<string, string | undefined> | undefined)?.['etag'] ??
      (response.headers as Record<string, string | undefined> | undefined)?.['ETag'] ??
      null;
    return { ...response.data, etag };
  },

  /**
   * Create a new contract
   */
  async create(data: ContractCreateRequest): Promise<Contract> {
    const response = await apiClient.getClient().post<Contract>(`${CONTRACTS_BASE_PATH}/`, data);
    return response.data;
  },

  /**
   * Update a contract.
   *
   * Phase 227 Wave 1 (227.L4.3 + 227.L5.6) — supports optional
   * ``If-Match`` header for optimistic concurrency. The backend
   * compares against the contract's current weak ETag and returns
   * HTTP 412 ``PRECONDITION_FAILED`` when stale; the editor's
   * conflict-dialog flow consumes that error.
   *
   * Returns ``{...contract, etag?}`` — the new ETag value is taken
   * from the ``ETag`` response header so callers can chain the next
   * PATCH without a fresh GET.
   */
  async update(
    id: string,
    data: ContractUpdateRequest,
    opts: { ifMatch?: string | null } = {},
  ): Promise<Contract & { etag?: string | null }> {
    const headers: Record<string, string> = {};
    if (opts.ifMatch) {
      headers['If-Match'] = opts.ifMatch;
    }
    const response = await apiClient
      .getClient()
      .patch<Contract>(`${CONTRACTS_BASE_PATH}/${id}/`, data, { headers });
    // The backend emits a fresh ETag header on every successful PATCH;
    // surface it on the returned object so the editor can update its
    // stored value without an extra GET.
    const etag =
      (response.headers as Record<string, string | undefined> | undefined)?.['etag'] ??
      (response.headers as Record<string, string | undefined> | undefined)?.['ETag'] ??
      null;
    return { ...response.data, etag };
  },

  /**
   * Delete a contract
   */
  async delete(id: string): Promise<void> {
    await apiClient.getClient().delete(`${CONTRACTS_BASE_PATH}/${id}/`);
  },

  /**
   * Phase 227 Wave 1 (227.L5.4) — fetch the canonical HubContract JSON
   * Schema. The Schema editor uses this to drive client-side validation
   * (allowed ``data_type`` enum, required fields, alias renames) so the
   * server + client speak the same Pydantic-defined contract.
   *
   * The optional ``spec`` query param is currently advisory — both
   * values return the same canonical schema; the editor compiles to
   * either ODCS or ODPS source via the client-side compiler.
   */
  async getJsonSchema(spec?: 'odcs' | 'odps'): Promise<{
    spec: 'odcs' | 'odps' | null;
    schema: Record<string, unknown>;
  }> {
    const path = spec
      ? `${CONTRACTS_BASE_PATH}/schema/json-schema/?spec=${spec}`
      : `${CONTRACTS_BASE_PATH}/schema/json-schema/`;
    const response = await apiClient
      .getClient()
      .get<{ spec: 'odcs' | 'odps' | null; schema: Record<string, unknown> }>(path);
    return response.data;
  },

  /**
   * Validate a contract draft without persisting (Phase 219.4).
   * Dry-run normalization — returns spec detection and errors/warnings.
   */
  async validateDraft(data: {
    original_raw: string;
    original_format: string;
  }): Promise<DraftValidationResult> {
    const response = await apiClient
      .getClient()
      .post<DraftValidationResult>(
        `${CONTRACTS_BASE_PATH}/validate-draft/`,
        data,
      );
    return response.data;
  },

  /**
   * Validate a contract
   */
  async validate(id: string): Promise<ContractValidationResult> {
    const response = await apiClient.getClient().post<ContractValidationResult>(
      `${CONTRACTS_BASE_PATH}/${id}/validate/`
    );
    return response.data;
  },

  /**
   * Lint a contract
   */
  async lint(id: string): Promise<ContractLintResult> {
    const response = await apiClient.getClient().post<ContractLintResult>(
      `${CONTRACTS_BASE_PATH}/${id}/lint/`
    );
    return response.data;
  },

  /**
   * Convert a contract format
   */
  async convert(id: string, data: ContractConvertRequest): Promise<ContractConvertResult> {
    const response = await apiClient.getClient().post<ContractConvertResult>(
      `${CONTRACTS_BASE_PATH}/${id}/convert/`,
      data
    );
    return response.data;
  },

  /**
   * Export a contract
   */
  async export(id: string, format?: string): Promise<Blob> {
    const url = format
      ? `${CONTRACTS_BASE_PATH}/${id}/export/?format=${format}`
      : `${CONTRACTS_BASE_PATH}/${id}/export/`;
    
    const response = await apiClient.getClient().get<Blob>(url, {
      responseType: 'blob',
    });
    return response.data;
  },

  /**
   * Download a contract
   */
  async download(id: string, format?: string): Promise<Blob> {
    const url = format
      ? `${CONTRACTS_BASE_PATH}/${id}/download/?format=${format}`
      : `${CONTRACTS_BASE_PATH}/${id}/download/`;
    
    const response = await apiClient.getClient().get<Blob>(url, {
      responseType: 'blob',
    });
    return response.data;
  },

  // ---------------------------------------------------------------------------
  // ODPS-specific operations (merged from odpsService.ts)
  // ---------------------------------------------------------------------------

  /**
   * Create ODPS product (Product-First flow)
   * POST /api/v1/contracts/products/
   */
  async createODPSProduct(data: ODPSProductCreateRequest): Promise<ODPSProductCreateResponse> {
    const response = await apiClient.getClient().post<ODPSProductCreateResponse>(
      `${CONTRACTS_BASE_PATH}/products/`,
      {
        original_raw: data.original_raw,
        original_format: data.original_format,
        resolve_external_refs: data.resolve_external_refs ?? true,
        asset_id: data.asset_id,
      },
      { timeout: 120000 }
    );
    return response.data;
  },

  /**
   * Get ODPS workflow status
   * GET /api/v1/contracts/products/workflows/{workflow_instance_id}/status/
   */
  async getWorkflowStatus(workflowInstanceId: string): Promise<ODPSWorkflowStatus> {
    const response = await apiClient.getClient().get<ODPSWorkflowStatus>(
      `${CONTRACTS_BASE_PATH}/products/workflows/${workflowInstanceId}/status/`
    );
    return response.data;
  },

  /**
   * Link ODPS to ODCS contract
   * POST /api/v1/contracts/{odcs_contract_id}/link-odps/
   */
  async linkODPS(odcsContractId: string, data: ODPSLinkRequest): Promise<ODPSLinkResponse> {
    const response = await apiClient.getClient().post<ODPSLinkResponse>(
      `${CONTRACTS_BASE_PATH}/${odcsContractId}/link-odps/`,
      {
        odps_contract_id: data.odps_contract_id,
        original_raw: data.original_raw,
        original_format: data.original_format,
        resolve_external_refs: data.resolve_external_refs ?? true,
      }
    );
    return response.data;
  },

  /**
   * Unlink ODPS from ODCS contract
   * POST /api/v1/contracts/{odcs_contract_id}/unlink-odps/
   */
  async unlinkODPS(odcsContractId: string): Promise<{ message: string }> {
    const response = await apiClient.getClient().post<{ message: string }>(
      `${CONTRACTS_BASE_PATH}/${odcsContractId}/unlink-odps/`
    );
    return response.data;
  },

  /**
   * Get contract links (ODPS ↔ ODCS)
   * GET /api/v1/contracts/{id}/links/
   */
  async getLinks(contractId: string): Promise<ODPSLinks> {
    const response = await apiClient.getClient().get<ODPSLinks>(
      `${CONTRACTS_BASE_PATH}/${contractId}/links/`
    );
    return response.data;
  },

  /**
   * Export ODPS contract with format options
   * GET /api/v1/contracts/{id}/export/?format=odps&output_format=json|yaml
   */
  async exportODPS(contractId: string, params: ODPSExportParams = {}): Promise<Blob> {
    const queryParams = new URLSearchParams();
    queryParams.append('format', params.format || 'odps');
    if (params.output_format) queryParams.append('output_format', params.output_format);
    if (params.version) queryParams.append('version', params.version);
    const response = await apiClient.getClient().get<Blob>(
      `${CONTRACTS_BASE_PATH}/${contractId}/export/?${queryParams.toString()}`,
      { responseType: 'blob' }
    );
    return response.data;
  },

  /**
   * Download ODPS contract with format options
   * GET /api/v1/contracts/{id}/download/?format=odps&output_format=json|yaml
   */
  async downloadODPS(contractId: string, params: ODPSExportParams = {}): Promise<Blob> {
    const queryParams = new URLSearchParams();
    queryParams.append('format', params.format || 'odps');
    if (params.output_format) queryParams.append('output_format', params.output_format);
    if (params.version) queryParams.append('version', params.version);
    const response = await apiClient.getClient().get<Blob>(
      `${CONTRACTS_BASE_PATH}/${contractId}/download/?${queryParams.toString()}`,
      { responseType: 'blob' }
    );
    return response.data;
  },

  // ---------------------------------------------------------------------------
  // Lineage
  // ---------------------------------------------------------------------------

  /**
   * Get contract lineage visualization (GET /api/v1/contracts/{id}/lineage/visualization/)
   * Returns nodes and links for graph visualization; no stub data.
   */
  async getLineageVisualization(
    id: string,
    params: ContractLineageVisualizationParams = {}
  ): Promise<ContractLineageVisualization> {
    const search = new URLSearchParams();
    search.set('format', params.format ?? 'json');
    if (params.max_depth != null) search.set('max_depth', String(params.max_depth));
    // Phase 228 F5 (228.F5.2) — surface the point-in-time knobs.
    if (params.as_of) search.set('as_of', params.as_of);
    if (params.version != null) search.set('version', String(params.version));
    if (params.include_fields) search.set('include_fields', 'true');
    const url = `${CONTRACTS_BASE_PATH}/${id}/lineage/visualization/?${search.toString()}`;
    const response = await apiClient.getClient().get<ContractLineageVisualization>(url);
    return response.data;
  },

  /**
   * Phase 228 F5 (228.F5.3) — point-in-time lineage diff.
   *
   * GET /api/v1/contracts/{id}/lineage/diff/?from=&to=
   *
   * Anchors accept either ISO-8601 (`from=2026-04-30T00:00:00Z`) or
   * version int (`from_version=3`). `to` defaults to NOW() server-side.
   */
  async getLineageDiff(
    id: string,
    params: import('../../../shared/types/lineage').ContractLineageDiffParams = {},
  ): Promise<import('../../../shared/types/lineage').LineageDiff> {
    const search = new URLSearchParams();
    if (params.from) search.set('from', params.from);
    if (params.to) search.set('to', params.to);
    if (params.from_version != null) search.set('from_version', String(params.from_version));
    if (params.to_version != null) search.set('to_version', String(params.to_version));
    const url = `${CONTRACTS_BASE_PATH}/${id}/lineage/diff/?${search.toString()}`;
    const response = await apiClient
      .getClient()
      .get<import('../../../shared/types/lineage').LineageDiff>(url);
    return response.data;
  },

  /**
   * Phase 228.F2.21 — update a contract's lineage.
   *
   * Sends a `PATCH /api/v1/contracts/{id}/lineage/` with the FULL
   * desired post-patch edge list (the server diffs against current
   * state).  Carries the optional `If-Match` header for ETag
   * concurrency and an optional `Idempotency-Key` for 24h replay
   * deduplication on the bug-prevention layer.
   *
   * Returns `{ contract_id, edges, added, removed, kept }`.
   */
  async updateLineage(
    id: string,
    payload: { edges: Array<Record<string, unknown>> },
    options: { ifMatch?: string; idempotencyKey?: string } = {},
  ): Promise<{
    contract_id: string;
    edges: Array<Record<string, unknown>>;
    added: number;
    removed: number;
    kept: number;
  }> {
    const headers: Record<string, string> = {};
    if (options.ifMatch) headers['If-Match'] = options.ifMatch;
    if (options.idempotencyKey) {
      headers['Idempotency-Key'] = options.idempotencyKey;
    }
    const response = await apiClient.getClient().patch<{
      contract_id: string;
      edges: Array<Record<string, unknown>>;
      added: number;
      removed: number;
      kept: number;
    }>(
      `${CONTRACTS_BASE_PATH}/${id}/lineage/`,
      payload,
      { headers },
    );
    return response.data;
  },
};
