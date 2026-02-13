/**
 * Observability Service
 * API client for observability endpoints (freshness, volume, SLAs, incidents)
 */

import { apiClient } from '../../../shared/api/client';
import type {
  FreshnessDashboard,
  IncidentsDashboard,
  ObservabilityFreshnessFilters,
  ObservabilityIncidentsFilters,
  ObservabilitySlasFilters,
  ObservabilityVolumeFilters,
  SlasDashboard,
  VolumeDashboard,
} from '../../../shared/types/observability';

const OBSERVABILITY_BASE = 'observability';

export const observabilityService = {
  /**
   * GET /api/v1/observability/freshness/
   */
  async getFreshnessDashboard(
    filters: ObservabilityFreshnessFilters = {}
  ): Promise<FreshnessDashboard> {
    const params = new URLSearchParams();
    if (filters.dataset_id) params.set('dataset_id', filters.dataset_id);
    if (filters.asset_id) params.set('asset_id', filters.asset_id);
    if (filters.limit != null) params.set('limit', String(filters.limit));
    const qs = params.toString();
    const url = qs ? `${OBSERVABILITY_BASE}/freshness/?${qs}` : `${OBSERVABILITY_BASE}/freshness/`;
    const { data } = await apiClient.getClient().get<FreshnessDashboard>(url);
    return data;
  },

  /**
   * GET /api/v1/observability/volume/
   */
  async getVolumeDashboard(filters: ObservabilityVolumeFilters = {}): Promise<VolumeDashboard> {
    const params = new URLSearchParams();
    if (filters.dataset_id) params.set('dataset_id', filters.dataset_id);
    if (filters.asset_id) params.set('asset_id', filters.asset_id);
    if (filters.period_type) params.set('period_type', filters.period_type);
    if (filters.limit != null) params.set('limit', String(filters.limit));
    const qs = params.toString();
    const url = qs ? `${OBSERVABILITY_BASE}/volume/?${qs}` : `${OBSERVABILITY_BASE}/volume/`;
    const { data } = await apiClient.getClient().get<VolumeDashboard>(url);
    return data;
  },

  /**
   * GET /api/v1/observability/slas/
   */
  async getSlasDashboard(filters: ObservabilitySlasFilters = {}): Promise<SlasDashboard> {
    const params = new URLSearchParams();
    if (filters.sla_type) params.set('sla_type', filters.sla_type);
    if (filters.dataset_id) params.set('dataset_id', filters.dataset_id);
    if (filters.asset_id) params.set('asset_id', filters.asset_id);
    if (filters.is_active != null) params.set('is_active', String(filters.is_active));
    if (filters.is_violated != null) params.set('is_violated', String(filters.is_violated));
    if (filters.limit != null) params.set('limit', String(filters.limit));
    const qs = params.toString();
    const url = qs ? `${OBSERVABILITY_BASE}/slas/?${qs}` : `${OBSERVABILITY_BASE}/slas/`;
    const { data } = await apiClient.getClient().get<SlasDashboard>(url);
    return data;
  },

  /**
   * GET /api/v1/observability/incidents/
   */
  async getIncidentsDashboard(
    filters: ObservabilityIncidentsFilters = {}
  ): Promise<IncidentsDashboard> {
    const params = new URLSearchParams();
    if (filters.status) params.set('status', filters.status);
    if (filters.incident_type) params.set('incident_type', filters.incident_type);
    if (filters.severity) params.set('severity', filters.severity);
    if (filters.assigned_to_id) params.set('assigned_to_id', filters.assigned_to_id);
    if (filters.resource_type) params.set('resource_type', filters.resource_type);
    if (filters.resource_id) params.set('resource_id', filters.resource_id);
    if (filters.limit != null) params.set('limit', String(filters.limit));
    const qs = params.toString();
    const url = qs ? `${OBSERVABILITY_BASE}/incidents/?${qs}` : `${OBSERVABILITY_BASE}/incidents/`;
    const { data } = await apiClient.getClient().get<IncidentsDashboard>(url);
    return data;
  },
};
