/**
 * GDPR Service
 * Data export (GDPR Article 20) and erasure (GDPR Article 17) requests.
 * API: /api/v1/users/me/export-jobs/ and /api/v1/users/me/erasure-requests/
 */

import { apiClient } from '../../../shared/api/client';
import type {
  DataExportJob,
  ErasureRequest,
  ExportDataResponse,
  RequestErasureResponse,
} from '../../../shared/types/gdpr';

const EXPORT_JOBS_BASE = '/users/me/export-jobs';
const ERASURE_REQUESTS_BASE = '/users/me/erasure-requests';

export const gdprService = {
  /** POST /users/me/export-jobs/export-data/ — request data export (GDPR Article 20) */
  async requestExport(): Promise<ExportDataResponse> {
    const response = await apiClient.getClient().post<ExportDataResponse>(
      `${EXPORT_JOBS_BASE}/export-data/`
    );
    return response.data;
  },

  /** GET /users/me/export-jobs/ — list export jobs */
  async listExportJobs(params?: {
    page?: number;
    page_size?: number;
  }): Promise<{ count: number; page: number; page_size: number; total_pages: number; results: DataExportJob[] }> {
    const searchParams = new URLSearchParams();
    if (params?.page != null) searchParams.set('page', String(params.page));
    if (params?.page_size != null) searchParams.set('page_size', String(params.page_size));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    const response = await apiClient
      .getClient()
      .get<{ count: number; page: number; page_size: number; total_pages: number; results: DataExportJob[] }>(
        `${EXPORT_JOBS_BASE}/${query}`
      );
    return response.data;
  },

  /** GET /users/me/export-jobs/{id}/ — get export job */
  async getExportJob(id: string): Promise<DataExportJob> {
    const response = await apiClient.getClient().get<DataExportJob>(`${EXPORT_JOBS_BASE}/${id}/`);
    return response.data;
  },

  /** POST /users/me/erasure-requests/request-erasure/ — request erasure (GDPR Article 17) */
  async requestErasure(): Promise<RequestErasureResponse> {
    const response = await apiClient
      .getClient()
      .post<RequestErasureResponse>(`${ERASURE_REQUESTS_BASE}/request-erasure/`);
    return response.data;
  },

  /** GET /users/me/erasure-requests/ — list erasure requests */
  async listErasureRequests(params?: {
    page?: number;
    page_size?: number;
  }): Promise<{ count: number; page: number; page_size: number; total_pages: number; results: ErasureRequest[] }> {
    const searchParams = new URLSearchParams();
    if (params?.page != null) searchParams.set('page', String(params.page));
    if (params?.page_size != null) searchParams.set('page_size', String(params.page_size));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    const response = await apiClient
      .getClient()
      .get<{ count: number; page: number; page_size: number; total_pages: number; results: ErasureRequest[] }>(
        `${ERASURE_REQUESTS_BASE}/${query}`
      );
    return response.data;
  },
};
