/**
 * Dataset Types
 * Based on backend DatasetSerializer and Dataset model
 */

export const DatasetFormat = {
  CSV: 'CSV',
  JSON: 'JSON',
  PARQUET: 'PARQUET',
} as const;
export type DatasetFormat = (typeof DatasetFormat)[keyof typeof DatasetFormat];

/** Mirrors hub/apps/datasets/models.py ``DatasetStatus`` (TextChoices). */
export const DatasetStatus = {
  ACTIVE: 'ACTIVE',
  RETIRED: 'RETIRED',
  DRAFT: 'DRAFT',
  PROCESSING: 'PROCESSING',
} as const;
export type DatasetStatus = (typeof DatasetStatus)[keyof typeof DatasetStatus];

export interface SchemaField {
  name: string;
  type: string;
  nullable: boolean;
  format?: string;
  pattern?: string;
  enum?: string[];
  semantic_type?: string;
}

export interface DatasetSchema {
  fields: SchemaField[];
}

export interface Dataset {
  id: string;
  name: string;
  description?: string;
  format: DatasetFormat;
  size_bytes: number;
  row_count?: number;
  schema?: DatasetSchema;
  version: string;
  created_at: string;
  updated_at: string;
  /** Asset UUID (API may return as "asset" or "asset_id") */
  asset_id?: string;
  asset?: string;
  /** Asset name when API returns it (e.g. nested serializer) */
  asset_name?: string;
  tenant_id: string;
  file_id?: string;
  // Phase 230 (REQ-SEM-DISCO-001 / 230.1.2) — canonical IRI emitted
  // by hub/apps/datasets/serializers.py:19.
  canonical_iri?: string;
  // Phase 260.4.A — dataset lifecycle (ACTIVE / RETIRED / DRAFT / PROCESSING).
  status?: DatasetStatus;
  /** Set by the retire endpoint (POST /datasets/{id}/retire/) once. */
  retired_at?: string | null;
}

export interface DatasetCreateRequest {
  file_id: string;
  asset_id?: string;
}

export interface DatasetUpdateRequest {
  /** Asset UUID to link; null or empty to unlink. Backend field is "asset". */
  asset_id?: string | null;
  /** @deprecated Use asset_id. Sent as "asset" to API for compatibility. */
  asset?: string | null;
}

export interface DatasetListFilters {
  page?: number;
  page_size?: number;
  ordering?: string;
  search?: string;
  asset_id?: string;
  format?: DatasetFormat;
  /** Phase 260.4.A.3 — when true, RETIRED datasets are included (backend opt-in). */
  include_retired?: boolean;
}

export interface DatasetVersion {
  id: string;
  version: string;
  created_at: string;
  updated_at: string;
  schema?: DatasetSchema;
  row_count?: number;
  size_bytes: number;
}

/**
 * GET /api/v1/datasets/{id}/versions/compare/ response — schema-evolution
 * shape computed by hub/apps/datasets/views.py::compare_versions via
 * SchemaEvolutionTracker (compatibility_level + summary + changes).
 */
export interface DatasetVersionCompareResult {
  version1: DatasetVersion;
  version2: DatasetVersion;
  compatibility_level: string;
  summary: Record<string, number>;
  changes: DatasetSchemaEvolutionChange[];
}

export interface DatasetSchemaEvolutionChange {
  field_name?: string;
  old_type?: string;
  new_type?: string;
  type?: string;
  is_breaking?: boolean;
  description?: string;
  old_value?: unknown;
  new_value?: unknown;
  breaking?: boolean;
}
