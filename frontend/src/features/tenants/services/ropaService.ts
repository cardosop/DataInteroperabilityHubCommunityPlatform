/**
 * Phase 232.4 — RoPA (Record of Processing Activities) API
 */
import { apiClient } from '../../../shared/api/client';

const ROPA_BASE = 'ropa/generations';

export interface RopaPreviewResponse {
  regulation: string;
  gaps: Array<{ code: string; asset_key?: string; message: string; fix_path?: string }>;
  summary: { asset_count?: number; gap_count?: number };
  cache_version?: number;
  cache_hit?: boolean;
}

export interface RopaGenerationRow {
  id: string;
  regulation: string;
  output_format: string;
  status: string;
  byte_size: number;
  content_sha256: string;
  gaps_json: unknown[];
  summary_json: Record<string, unknown>;
  job?: string | null;
  created_at: string;
  completed_at: string | null;
  error_message: string;
}

export const ropaService = {
  async preview(regulation = 'GDPR'): Promise<RopaPreviewResponse> {
    const r = await apiClient.getClient().get<RopaPreviewResponse>(`${ROPA_BASE}/preview/`, {
      params: { regulation },
    });
    return r.data;
  },

  async generate(regulation: string, format: string) {
    return apiClient.getClient().post('/ropa/generate/', null, {
      params: { regulation, format },
    });
  },

  async listGenerations(): Promise<{ results?: RopaGenerationRow[] }> {
    return (await apiClient.getClient().get<{ results?: RopaGenerationRow[] }>(`${ROPA_BASE}/`)).data;
  },

  async downloadUrl(id: string): Promise<{ download_url: string; expires_in: number }> {
    const r = await apiClient.getClient().get<{ download_url: string; expires_in: number }>(
      `${ROPA_BASE}/${id}/download/`
    );
    return r.data;
  },
};
