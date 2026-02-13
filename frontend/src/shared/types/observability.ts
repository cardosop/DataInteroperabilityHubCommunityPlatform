/**
 * Observability API types (aligned with backend OpenAPI / serializers)
 */

export interface FreshnessMetric {
  id: string;
  dataset_id?: string;
  asset_id?: string;
  last_update_time?: string;
  freshness_age_seconds?: number;
  freshness_sla?: string;
  freshness_sla_seconds?: number;
  is_stale?: boolean;
  recorded_at?: string;
}

export interface FreshnessDashboard {
  results: FreshnessMetric[];
  summary: Record<string, unknown>;
}

export interface VolumeTrend {
  id: string;
  dataset_id?: string;
  asset_id?: string;
  period_start: string;
  period_end: string;
  period_type: string;
  avg_row_count?: number;
  min_row_count?: number;
  max_row_count?: number;
  avg_size_bytes?: number;
  min_size_bytes?: number;
  max_size_bytes?: number;
  sample_count?: number;
  is_anomaly?: boolean;
  anomaly_type?: string | null;
  anomaly_score?: number | null;
  created_at?: string;
}

export interface VolumeDashboard {
  results: VolumeTrend[];
  summary: Record<string, unknown>;
}

export interface SchemaDriftItem {
  id: string;
  dataset_id?: string;
  asset_id?: string;
  previous_schema_hash?: string;
  current_schema_hash?: string;
  new_fields?: string[];
  removed_fields?: string[];
  type_changes?: Record<string, unknown>;
  nullable_changes?: Record<string, unknown>;
  drift_severity?: string;
  tolerance_config?: Record<string, unknown>;
  is_within_tolerance?: boolean;
  detected_at?: string;
}

export interface SchemaDriftDashboard {
  results: SchemaDriftItem[];
  summary: Record<string, unknown>;
}

export interface ObservabilityFreshnessFilters {
  dataset_id?: string;
  asset_id?: string;
  limit?: number;
}

export interface ObservabilityVolumeFilters {
  dataset_id?: string;
  asset_id?: string;
  period_type?: 'HOURLY' | 'DAILY';
  limit?: number;
}

export interface ObservabilitySlasFilters {
  sla_type?: string;
  dataset_id?: string;
  asset_id?: string;
  is_active?: boolean;
  is_violated?: boolean;
  limit?: number;
}

export interface ObservabilityIncidentsFilters {
  status?: string;
  incident_type?: string;
  severity?: string;
  assigned_to_id?: string;
  resource_type?: string;
  resource_id?: string;
  limit?: number;
}

/** SLAs and incidents dashboards: backend returns generic dashboard object */
export type SlasDashboard = Record<string, unknown> & {
  results?: unknown[];
  summary?: Record<string, unknown>;
};

export type IncidentsDashboard = Record<string, unknown> & {
  results?: unknown[];
  summary?: Record<string, unknown>;
};
