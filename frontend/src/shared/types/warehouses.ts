/**
 * Warehouse Types — Phase 275
 * Based on hub/apps/warehouses/models.py
 */

export const WarehouseType = {
  SNOWFLAKE: 'SNOWFLAKE',
  BIGQUERY: 'BIGQUERY',
  DATABRICKS: 'DATABRICKS',
  ATHENA: 'ATHENA',
} as const;
export type WarehouseType = (typeof WarehouseType)[keyof typeof WarehouseType];

export const WarehouseConnectionACLRole = {
  ADMIN: 'ADMIN',
  OPERATOR: 'OPERATOR',
  VIEWER: 'VIEWER',
} as const;
export type WarehouseConnectionACLRole =
  (typeof WarehouseConnectionACLRole)[keyof typeof WarehouseConnectionACLRole];

export interface WarehouseConnection {
  id: string;
  tenant: string;
  name: string;
  warehouse_type: WarehouseType;
  warehouse_type_display: string;
  region: string;
  private_endpoint_url: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WarehouseConnectionCreatePayload {
  name: string;
  warehouse_type: WarehouseType;
  config: Record<string, unknown>;
  region?: string;
  private_endpoint_url?: string;
  is_active?: boolean;
}

export interface WarehouseConnectionTestResult {
  success: boolean;
  latency_ms?: number;
  warehouse_type: string;
  error?: string;
  tested_at?: string;
}

export interface SchemaColumn {
  name: string;
  data_type: string;
  nullable: boolean;
  comment: string;
}

export interface SchemaReflection {
  connection_id: string;
  table: string;
  warehouse_type: string;
  columns: SchemaColumn[];
  reflected_at: string;
}

export interface WarehouseConnectionACL {
  id: string;
  tenant: string;
  connection: string;
  user: string;
  role: WarehouseConnectionACLRole;
  created_at: string;
}

export interface DeltaShareTable {
  name: string;
  share: string;
  schema: string;
}

export interface ResidencyMismatch {
  tenant_id: string;
  connection_id: string;
  connection_name: string;
  tenant_region: string;
  warehouse_region: string;
}
