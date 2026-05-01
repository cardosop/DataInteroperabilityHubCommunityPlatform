/**
 * Lineage types
 * Aligned with backend GET /api/v1/contracts/{id}/lineage/visualization/?format=json
 * Response shape: { nodes, links } (backend uses "links" not "edges")
 */

export type ContractLineageNodeType = 'contract' | 'model' | 'field';

export interface ContractLineageNode {
  id: string;
  type: ContractLineageNodeType;
  name: string | null;
  label: string | null;
  contract_id?: string;
}

export interface ContractLineageLink {
  source: string;
  target: string;
}

export interface ContractLineageVisualization {
  nodes: ContractLineageNode[];
  links: ContractLineageLink[];
}

export interface ContractLineageVisualizationParams {
  format?: 'json' | 'dot' | 'mermaid';
  max_depth?: number;
}

// ---------------------------------------------------------------------------
// Phase 228.F1 (REQ-LIN-F1-001 / F1.16) — listing-lineage tier types
// ---------------------------------------------------------------------------

/**
 * Detail tier for cross-tenant marketplace lineage.
 *
 * - `summary`: pre-purchase view; transformation IP stripped on the
 *   server side (no `transformation_ref` / `job_ref` /
 *   `created_by_run` / `source_field` / `target_field` in the
 *   response).
 * - `full`: post-purchase view; available only when the consumer
 *   tenant holds an ACTIVE Entitlement for the listing's backing
 *   asset.
 */
export type LineageDetailLevel = 'summary' | 'full';

/** Wire-format link as returned by `GET /listings/{id}/lineage/`. */
export interface ListingLineageLink {
  source: string;
  target: string;
  edge_type: string;
  // Full-tier-only fields — absent on summary responses (the
  // backend's `LineageGraphSummarySerializer` field allowlist
  // makes these structurally impossible at the summary tier).
  transformation_ref?: string;
  job_ref?: string;
  created_by_run?: string;
  source_field?: string;
  target_field?: string;
}

export interface ListingLineageNode {
  id: string;
  type: 'contract' | 'external' | string;
  label: string;
}

export interface ListingLineageGraph {
  nodes: ListingLineageNode[];
  links: ListingLineageLink[];
  truncated: boolean;
  detail: LineageDetailLevel;
}

export interface ListingLineageParams {
  detail?: LineageDetailLevel;
  max_depth?: number;
}
