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
  asset_id?: string;
  tenant_id: string;
  file_id?: string;
}

export interface DatasetCreateRequest {
  file_id: string;
  asset_id?: string;
}

export interface DatasetUpdateRequest {
  name?: string;
  description?: string;
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
