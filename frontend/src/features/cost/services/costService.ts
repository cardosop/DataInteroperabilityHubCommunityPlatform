/**
 * Cost Tracking Service (UC-TA-007)
 * API client for cost tracking endpoints
 * GET /api/v1/analytics/costs/
 */

import { apiClient } from '../../../shared/api/client';
import type {
  CostByAsset,
  CostRecommendations,
  CostSummary,
  CostTrends,
} from '../../../shared/types/cost';

const ANALYTICS_BASE = 'analytics/costs';

export const costService = {
  /**
   * Get cost summary for tenant
   */
  async getSummary(params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<CostSummary> {
    const searchParams = new URLSearchParams();
    if (params?.start_date) searchParams.set('start_date', params.start_date);
    if (params?.end_date) searchParams.set('end_date', params.end_date);
    const qs = searchParams.toString();
    const url = qs ? `${ANALYTICS_BASE}/?${qs}` : `${ANALYTICS_BASE}/`;
    const response = await apiClient.getClient().get<CostSummary>(url);
    return response.data;
  },

  /**
   * Get cost breakdown by category
   */
  async getBreakdown(params?: {
    period?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<CostSummary> {
    const searchParams = new URLSearchParams();
    if (params?.period) searchParams.set('period', params.period);
    if (params?.start_date) searchParams.set('start_date', params.start_date);
    if (params?.end_date) searchParams.set('end_date', params.end_date);
    const qs = searchParams.toString();
    const url = qs ? `${ANALYTICS_BASE}/breakdown/?${qs}` : `${ANALYTICS_BASE}/breakdown/`;
    const response = await apiClient.getClient().get<CostSummary>(url);
    return response.data;
  },

  /**
   * Get cost by asset
   */
  async getByAsset(params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<CostByAsset> {
    const searchParams = new URLSearchParams();
    if (params?.start_date) searchParams.set('start_date', params.start_date);
    if (params?.end_date) searchParams.set('end_date', params.end_date);
    const qs = searchParams.toString();
    const url = qs ? `${ANALYTICS_BASE}/by-asset/?${qs}` : `${ANALYTICS_BASE}/by-asset/`;
    const response = await apiClient.getClient().get<CostByAsset>(url);
    return response.data;
  },

  /**
   * Get cost optimization recommendations
   */
  async getRecommendations(): Promise<CostRecommendations> {
    const response = await apiClient
      .getClient()
      .get<CostRecommendations>(`${ANALYTICS_BASE}/recommendations/`);
    return response.data;
  },

  /**
   * Get cost trends over time
   */
  async getTrends(params?: { period?: string; months?: number }): Promise<CostTrends> {
    const searchParams = new URLSearchParams();
    if (params?.period) searchParams.set('period', params.period);
    if (params?.months != null) searchParams.set('months', String(params.months));
    const qs = searchParams.toString();
    const url = qs ? `${ANALYTICS_BASE}/trends/?${qs}` : `${ANALYTICS_BASE}/trends/`;
    const response = await apiClient.getClient().get<CostTrends>(url);
    return response.data;
  },
};
