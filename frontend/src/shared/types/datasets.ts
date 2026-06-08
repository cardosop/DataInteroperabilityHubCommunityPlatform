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
}

export interface DatasetVersion {
  version: string;
  created_at: string;
  updated_at: string;
  schema?: DatasetSchema;
  row_count?: number;
  size_bytes: number;
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
