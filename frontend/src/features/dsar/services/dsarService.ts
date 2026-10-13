/**
 * Phase 232.2 — DSAR (handler-side) API client.
 *
 * Public-portal endpoints (`/legal/dsar`) live elsewhere — this module
 * is the TENANT_ADMIN / DPO / LEGAL_ADMIN handler surface (queue +
 * detail actions).
 *
 * Convention mirrors the rest of the repo: components import
 * `dsarService` and never reach into `apiClient` directly.
 */
import { apiClient } from '../../../shared/api/client';

// The DSAR handler API lives at /api/v1/dsar/requests/ (hub/apps/dsar/
// urls.py) — NOT under /governance/. close-test-coverage-gaps 4.4: the
// old 'governance/dsar-requests' base 404'd every queue/detail call once
// the compliance_dsar capability route started rendering for real.
const REQUESTS_BASE = 'dsar/requests';

// ---------------------------------------------------------------------------
// Response shapes
// ---------------------------------------------------------------------------

export interface DsarListRow {
  id: string;
  status: string;
  request_type: string;
  subject_email: string;
  statutory_fulfil_deadline_utc: string | null;
  subject_timezone?: string | null;
  regulator_timezone?: string | null;
  last_sla_level?: string | null;
  created_at?: string;
}

/** DRF-paginated or plain-array shape, depending on tenant config. */
export type DsarListResponse =
  | { results: DsarListRow[] }
  | DsarListRow[];

/** Detail payload — kept as `Record<string, unknown>` because the
 *  full DSAR detail surface is large and evolving; the handler page
 *  only reads a few well-known fields and narrows them at the call
 *  site. Tighten when the SDK regenerates against a stable schema. */
export type DsarDetail = Record<string, unknown>;

export interface DsarRejectRequest {
  reason: string;
}

export interface DsarLegalHoldRequest {
  active: boolean;
  reason: string;
}

export interface DsarIssueDownloadResponse {
  download_url: string;
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

export const dsarService = {
  async listRequests(): Promise<DsarListRow[]> {
    const res = await apiClient
      .getClient()
      .get<DsarListResponse>(`${REQUESTS_BASE}/`);
    const payload = res.data;
    return Array.isArray(payload) ? payload : payload.results ?? [];
  },

  async getRequest(id: string): Promise<DsarDetail> {
    const res = await apiClient
      .getClient()
      .get<DsarDetail>(`${REQUESTS_BASE}/${id}/`);
    return res.data;
  },

  async materializePackage(id: string): Promise<void> {
    await apiClient
      .getClient()
      .post(`${REQUESTS_BASE}/${id}/materialize_package/`);
  },

  async rejectRequest(id: string, payload: DsarRejectRequest): Promise<void> {
    await apiClient.getClient().post(`${REQUESTS_BASE}/${id}/reject/`, payload);
  },

  async setLegalHold(id: string, payload: DsarLegalHoldRequest): Promise<void> {
    await apiClient
      .getClient()
      .post(`${REQUESTS_BASE}/${id}/legal_hold/`, payload);
  },

  async issueDownloadUrl(id: string): Promise<DsarIssueDownloadResponse> {
    const res = await apiClient
      .getClient()
      .post<DsarIssueDownloadResponse>(
        `${REQUESTS_BASE}/${id}/issue_download_url/`,
      );
    return res.data;
  },
};
