/**
 * Phase 232.5 — DPIA API client
 */
import { apiClient } from '../../../shared/api/client';

const BASE = 'dpia/records';

export type DpiaStatus =
  | 'DRAFT'
  | 'IN_REVIEW'
  | 'APPROVED'
  | 'REJECTED'
  | 'REQUIRES_CONSULTATION'
  | 'SUPERSEDED';

export interface DpiaRow {
  id: string;
  title: string;
  regime: string;
  status: DpiaStatus;
  version: number;
  asset: string | null;
  wizard_payload: Record<string, unknown>;
  risk_residual: string;
  next_review_due_at: string | null;
  dpo_summary: string;
  created_at: string;
  updated_at: string;
}

/** Shape returned by `GET /dpia/records/{id}/diff/`. Promoted from
 *  an inline return type so the response can be referenced as a
 *  named generic argument and consumers can import it. */
export interface DpiaDiffResponse {
  changed_keys: { field: string; before: unknown; after: unknown }[];
  previous_id?: string;
  current_id?: string;
  detail?: string;
}

export interface AssetDpiaBadge {
  compliance_dpia_enabled: boolean;
  dpia_required: boolean;
  open_dpia_id: string | null;
  badge_message: string;
}

export const dpiaService = {
  async list(params?: { status?: string; page?: number }): Promise<{ results: DpiaRow[] }> {
    const res = await apiClient.getClient().get<{ results: DpiaRow[] }>(`/${BASE}/`, { params });
    return res.data;
  },

  async get(id: string): Promise<DpiaRow> {
    const res = await apiClient.getClient().get<DpiaRow>(`/${BASE}/${id}/`);
    return res.data;
  },

  async create(body: {
    title: string;
    regime?: string;
    asset?: string | null;
    wizard_payload?: Record<string, unknown>;
  }): Promise<DpiaRow> {
    const res = await apiClient.getClient().post<DpiaRow>(`/${BASE}/`, body);
    return res.data;
  },

  async patch(id: string, body: Partial<{ title: string; wizard_payload: Record<string, unknown> }>): Promise<DpiaRow> {
    const res = await apiClient.getClient().patch<DpiaRow>(`/${BASE}/${id}/`, body);
    return res.data;
  },

  async submit(id: string): Promise<DpiaRow> {
    const res = await apiClient.getClient().post<DpiaRow>(`/${BASE}/${id}/submit/`);
    return res.data;
  },

  async review(
    id: string,
    body: {
      outcome: DpiaStatus;
      risk_residual?: string;
      dpo_summary?: string;
    }
  ): Promise<DpiaRow> {
    const res = await apiClient.getClient().post<DpiaRow>(`/${BASE}/${id}/review/`, body);
    return res.data;
  },

  async completeConsultation(id: string, approve: boolean): Promise<DpiaRow> {
    const res = await apiClient.getClient().post<DpiaRow>(`/${BASE}/${id}/consultation/complete/`, {
      approve,
    });
    return res.data;
  },

  async diff(id: string): Promise<DpiaDiffResponse> {
    // Pass the generic to `.get<T>` so `res.data` is typed as
    // `DpiaDiffResponse` rather than `unknown`. Matches the convention
    // used by the other service methods in this file.
    const res = await apiClient.getClient().get<DpiaDiffResponse>(
      `/${BASE}/${id}/diff/`,
    );
    return res.data;
  },

  async assetStatus(assetId: string): Promise<AssetDpiaBadge> {
    const res = await apiClient.getClient().get<AssetDpiaBadge>(`/${BASE}/asset-status/`, {
      params: { asset_id: assetId },
    });
    return res.data;
  },
};
