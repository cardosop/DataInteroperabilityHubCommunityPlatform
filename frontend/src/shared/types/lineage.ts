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
  // Phase 228 F5 (228.F5.2) — point-in-time controls.
  /** ISO-8601 timestamp; renders the lineage graph at that historical state. */
  as_of?: string;
  /** Contract version int; resolves to that contract's `created_at` cutoff. */
  version?: number;
  /** Phase 228.F2 (228.F2.3) field-level node expansion (existing flag). */
  include_fields?: boolean;
}

// ---------------------------------------------------------------------------
// Phase 228 F5 (228.F5.3) — diff endpoint types.
// ---------------------------------------------------------------------------

export interface LineageDiffSummary {
  added: number;
  removed: number;
  /**
   * Always 0 per REQ-LIN-F5-002 (SCD-2 close-and-reopen).
   * Field kept on the type for forward-compatible clients.
   */
  modified: number;
  unchanged: number;
}

export interface LineageDiffEdge {
  id?: string;
  source_contract: string | null;
  target_contract: string | null;
  source_model?: string;
  source_field?: string;
  target_model?: string;
  target_field?: string;
  edge_type: string;
  transformation_ref?: string;
  job_ref?: string;
  valid_from?: string;
  valid_to?: string | null;
}

export interface LineageDiffAnchor {
  timestamp: string;
  source: 'timestamp' | 'version' | 'now';
}

export interface LineageDiff {
  added: LineageDiffEdge[];
  removed: LineageDiffEdge[];
  /**
   * Always `[]` per REQ-LIN-F5-002 — SCD-2 represents modifications
   * as close-and-reopen, so a "modified" edge surfaces as one
   * removed + one added.
   */
  modified: LineageDiffEdge[];
  unchanged: LineageDiffEdge[];
  summary: LineageDiffSummary;
  from: LineageDiffAnchor;
  to: LineageDiffAnchor;
}

export interface ContractLineageDiffParams {
  /** ISO-8601 timestamp for the older anchor. */
  from?: string;
  /** ISO-8601 timestamp for the newer anchor; defaults to now. */
  to?: string;
  /** Contract version int → resolves to its `created_at`. */
  from_version?: number;
  /** Contract version int → resolves to its `created_at`. */
  to_version?: number;
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
