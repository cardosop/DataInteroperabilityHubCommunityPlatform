/**
 * Cost Tracking Types (UC-TA-007)
 * Based on GET /api/v1/analytics/costs/ responses
 */

export interface CostBreakdownItem {
  category: string;
  amount_usd: number;
  quantity: number | null;
}

export interface CostSummary {
  tenant_id: string;
  total_cost: number;
  breakdown: CostBreakdownItem[];
  period_start: string;
  period_end: string;
  period: string;
}

export interface CostByAssetItem {
  asset_id: string;
  asset_name: string;
  asset_key: string;
  storage_bytes: number;
  storage_gb: number;
  cost_usd: number;
}

export interface CostByAsset {
  tenant_id: string;
  by_asset: CostByAssetItem[];
  total_cost: number;
}

export interface CostRecommendation {
  type: string;
  message: string;
  severity: 'info' | 'warning' | 'error';
}

export interface CostRecommendations {
  tenant_id: string;
  recommendations: CostRecommendation[];
}

export interface CostTrendItem {
  period_start: string;
  period_end: string;
  total_cost: number;
  breakdown: CostBreakdownItem[];
}

export interface CostTrends {
  tenant_id: string;
  trends: CostTrendItem[];
  period: string;
}
