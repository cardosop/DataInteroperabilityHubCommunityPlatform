/**
 * Marketplace Integration Types
 * Based on backend integration serializers and models
 */

export const MarketplaceType = {
  SNOWFLAKE_DATA_MARKETPLACE: 'SNOWFLAKE_DATA_MARKETPLACE',
  AWS_DATA_EXCHANGE: 'AWS_DATA_EXCHANGE',
  AZURE_DATA_SHARE: 'AZURE_DATA_SHARE',
  GCP_DATA_EXCHANGE: 'GCP_DATA_EXCHANGE',
  DATABRICKS_MARKETPLACE: 'DATABRICKS_MARKETPLACE',
  SALESFORCE_DATA_CLOUD: 'SALESFORCE_DATA_CLOUD',
  SAP_DATA_INTELLIGENCE: 'SAP_DATA_INTELLIGENCE',
  ORACLE_DATA_MARKETPLACE: 'ORACLE_DATA_MARKETPLACE',
  IBM_CLOUD_PAK: 'IBM_CLOUD_PAK',
  DATARADE: 'DATARADE',
  DAWEX: 'DAWEX',
  NASDAQ_DATA_LINK: 'NASDAQ_DATA_LINK',
  ESRI_ARCGIS: 'ESRI_ARCGIS',
  COLLIBRA: 'COLLIBRA',
  CKAN: 'CKAN',
} as const;

export type MarketplaceType = typeof MarketplaceType[keyof typeof MarketplaceType];

export const SyncDirection = {
  PUSH: 'PUSH',
  PULL: 'PULL',
  BIDIRECTIONAL: 'BIDIRECTIONAL',
} as const;

export type SyncDirection = typeof SyncDirection[keyof typeof SyncDirection];

export const SyncJobStatus = {
  PENDING: 'PENDING',
  RUNNING: 'RUNNING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  PARTIAL: 'PARTIAL',
  CANCELLED: 'CANCELLED',
} as const;

export type SyncJobStatus = typeof SyncJobStatus[keyof typeof SyncJobStatus];

export interface MarketplaceConnection {
  id: string;
  tenant: string;
  name: string;
  marketplace_type: MarketplaceType;
  config_json: Record<string, unknown>;
  is_active: boolean;
  last_sync_at?: string | null;
  created_at: string;
  updated_at: string;
  // Read-only fields (not in config_json)
  status?: string;
  error_message?: string | null;
}

export interface MarketplaceConnectionCreate {
  name: string;
  marketplace_type: MarketplaceType;
  config_json: Record<string, unknown>;
  is_active?: boolean;
}

export interface MarketplaceConnectionUpdate {
  name?: string;
  config_json?: Record<string, unknown>;
  is_active?: boolean;
}

export interface MarketplaceConnectionListFilters {
  page?: number;
  page_size?: number;
  ordering?: string;
  marketplace_type?: MarketplaceType;
  is_active?: boolean;
  search?: string;
}

export interface MarketplaceConnectionTestResponse {
  success: boolean;
  message: string;
  tested_at: string;
  details?: Record<string, unknown>;
  error?: string;
}

export interface MarketplaceSyncJob {
  id: string;
  connection: {
    id: string;
    name: string;
    marketplace_type: MarketplaceType;
  };
  direction: SyncDirection;
  status: SyncJobStatus;
  items_synced?: number;
  items_failed?: number;
  errors?: string[];
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  started_at?: string | null;
}

export interface MarketplaceSyncJobCreate {
  connection_id: string;
  direction: SyncDirection;
  asset_ids?: string[];
  options?: Record<string, unknown>;
}

export interface MarketplaceSyncJobCancel {
  reason?: string;
}

export interface MarketplaceSyncJobListFilters {
  page?: number;
  page_size?: number;
  ordering?: string;
  connection_id?: string;
  direction?: SyncDirection;
  status?: SyncJobStatus;
}

export interface MarketplaceMapping {
  id: string;
  connection: {
    id: string;
    name: string;
    marketplace_type: MarketplaceType;
  };
  hub_asset_id: string;
  external_listing_id: string;
  external_listing_url?: string | null;
  sync_metadata?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  last_synced_at?: string | null;
}

export interface MarketplaceMappingListFilters {
  page?: number;
  page_size?: number;
  ordering?: string;
  connection_id?: string;
  hub_asset_id?: string;
  external_listing_id?: string;
}

export interface MarketplaceConnector {
  type: MarketplaceType;
  display_name: string;
  description: string;
  supported_directions: SyncDirection[];
  status: string;
  config_schema?: Record<string, unknown>;
}
