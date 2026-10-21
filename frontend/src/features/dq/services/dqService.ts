/**
 * Data Quality Service
 * API client for DQ run + advanced quality endpoints (Phase 240.4.A).
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  DQAlertingRule,
  DQAlertingRuleCreateRequest,
  DQAlertingRuleUpdateRequest,
  DQAnomaliesFilters,
  DQAnomaly,
  DQAssetScorecard,
  DQExecutiveDashboard,
  DQRootCauseAnalysis,
  DQRootCauseFilters,
  DQRun,
  DQRunCreateRequest,
  DQRunListFilters,
  DQRunResults,
  DQTrendPoint,
  DQTrendsFilters,
} from '../../../shared/types/dq';

const DQ_BASE_PATH = 'dq/runs';
const DQ_QUALITY_BASE_PATH = 'dq/quality';
const DQ_ALERTING_RULES_PATH = 'dq/alerting-rules';

function buildQuery(params: Record<string, string | number | boolean | undefined | null>): string {
  const url = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      url.append(key, String(value));
    }
  }
  const qs = url.toString();
  return qs ? `?${qs}` : '';
}

export const dqService = {
  /**
   * List DQ runs with filtering and pagination
   */
  async list(filters: DQRunListFilters = {}): Promise<PaginatedResponse<DQRun>> {
    const params = new URLSearchParams();

    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.status) params.append('status', filters.status);
    if (filters.dataset_id) params.append('dataset_id', filters.dataset_id);
    if (filters.date_from) params.append('date_from', filters.date_from);
    if (filters.date_to) params.append('date_to', filters.date_to);

    const response = await apiClient.getClient().get<PaginatedResponse<DQRun>>(
      `${DQ_BASE_PATH}/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Get DQ run by ID
   */
  async getById(id: string): Promise<DQRun> {
    const response = await apiClient.getClient().get<DQRun>(`${DQ_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Create a new DQ run
   */
  async create(data: DQRunCreateRequest): Promise<DQRun> {
    const response = await apiClient.getClient().post<DQRun>(`${DQ_BASE_PATH}/`, data);
    return response.data;
  },

  /**
   * Get DQ run results
   */
  async getResults(id: string): Promise<DQRunResults> {
    const response = await apiClient.getClient().get<DQRunResults>(
      `${DQ_BASE_PATH}/${id}/results/`
    );
    return response.data;
  },

  // ─── Phase 240.4.A.6 — Advanced quality endpoints ──────────────────

  /**
   * GET /api/v1/dq/quality/anomalies/
   * Lists detected DQ anomalies for the requesting tenant.
   */
  async getAnomalies(filters: DQAnomaliesFilters = {}): Promise<{ results: DQAnomaly[] }> {
    const qs = buildQuery({
      asset_id: filters.asset_id,
      dataset_id: filters.dataset_id,
      severity: filters.severity,
      since: filters.since,
    });
    const response = await apiClient.getClient().get<{ results: DQAnomaly[] }>(
      `${DQ_QUALITY_BASE_PATH}/anomalies/${qs}`,
    );
    return response.data;
  },

  /**
   * GET /api/v1/dq/quality/trends/
   * Computes / lists quality trends for an asset or dataset.
   */
  async getTrends(filters: DQTrendsFilters = {}): Promise<{ results: DQTrendPoint[] }> {
    const qs = buildQuery({
      asset_id: filters.asset_id,
      dataset_id: filters.dataset_id,
      metric_type: filters.metric_type,
      time_range: filters.time_range,
      period_type: filters.period_type,
    });
    const response = await apiClient.getClient().get<{ results: DQTrendPoint[] }>(
      `${DQ_QUALITY_BASE_PATH}/trends/${qs}`,
    );
    return response.data;
  },

  /**
   * GET /api/v1/dq/quality/scorecards/
   * Returns an executive dashboard (no asset_id) or per-asset scorecard.
   *
   * The two response shapes are discriminated by the presence of
   * ``asset_id`` in the input — callers can narrow with the union return.
   */
  async getScorecards(
    filters: { asset_id?: string; time_range?: number } = {},
  ): Promise<DQExecutiveDashboard | DQAssetScorecard> {
    const qs = buildQuery({
      asset_id: filters.asset_id,
      time_range: filters.time_range,
    });
    const response = await apiClient.getClient().get<
      DQExecutiveDashboard | DQAssetScorecard
    >(`${DQ_QUALITY_BASE_PATH}/scorecards/${qs}`);
    return response.data;
  },

  /**
   * GET /api/v1/dq/quality/root_cause_analysis/
   * Returns a root-cause analysis report for a DQ run.
   * Either ``dq_run_id`` OR ``asset_id`` is required; if both are
   * supplied, ``dq_run_id`` wins (per backend semantics).
   */
  async getRootCauseAnalysis(filters: DQRootCauseFilters): Promise<DQRootCauseAnalysis> {
    const qs = buildQuery({
      dq_run_id: filters.dq_run_id,
      asset_id: filters.asset_id,
      lookback_days: filters.lookback_days,
    });
    const response = await apiClient.getClient().get<DQRootCauseAnalysis>(
      `${DQ_QUALITY_BASE_PATH}/root_cause_analysis/${qs}`,
    );
    return response.data;
  },

  // ─── Phase 240.4.A.6 — DQAlertingRule CRUD ──────────────────────────

  async listAlertingRules(filters: {
    asset_id?: string;
    enabled?: boolean;
  } = {}): Promise<PaginatedResponse<DQAlertingRule>> {
    const qs = buildQuery({
      asset_id: filters.asset_id,
      enabled: filters.enabled,
    });
    const response = await apiClient.getClient().get<PaginatedResponse<DQAlertingRule>>(
      `${DQ_ALERTING_RULES_PATH}/${qs}`,
    );
    return response.data;
  },

  async createAlertingRule(data: DQAlertingRuleCreateRequest): Promise<DQAlertingRule> {
    const response = await apiClient.getClient().post<DQAlertingRule>(
      `${DQ_ALERTING_RULES_PATH}/`,
      data,
    );
    return response.data;
  },

  async updateAlertingRule(
    id: string,
    data: DQAlertingRuleUpdateRequest,
  ): Promise<DQAlertingRule> {
    const response = await apiClient.getClient().patch<DQAlertingRule>(
      `${DQ_ALERTING_RULES_PATH}/${id}/`,
      data,
    );
    return response.data;
  },

  async deleteAlertingRule(id: string): Promise<void> {
    await apiClient.getClient().delete(`${DQ_ALERTING_RULES_PATH}/${id}/`);
  },
};
