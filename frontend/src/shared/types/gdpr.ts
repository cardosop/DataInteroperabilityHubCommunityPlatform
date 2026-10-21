/**
 * GDPR types for data export and erasure requests.
 * Maps to backend /api/v1/users/me/export-jobs/ and /api/v1/users/me/erasure-requests/
 */

export const DataExportStatus = {
  PENDING: 'PENDING',
  PROCESSING: 'PROCESSING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
} as const;

export type DataExportStatus = (typeof DataExportStatus)[keyof typeof DataExportStatus];

export const ErasureRequestStatus = {
  PENDING: 'PENDING',
  PROCESSING: 'PROCESSING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
} as const;

export type ErasureRequestStatus = (typeof ErasureRequestStatus)[keyof typeof ErasureRequestStatus];

export interface DataExportJob {
  id: string;
  user: string;
  tenant: string;
  status: DataExportStatus;
  storage_path?: string | null;
  download_url?: string | null;
  download_url_expires_at?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface ErasureRequest {
  id: string;
  user: string;
  tenant: string;
  status: ErasureRequestStatus;
  requested_at: string;
  completed_at?: string | null;
  error_message?: string | null;
  anonymized_fields?: string[];
  deleted_resources?: string[];
  retention_exceptions?: string[];
  created_at: string;
  updated_at: string;
}

/** Response from POST /users/me/export-jobs/export-data/ */
export interface ExportDataResponse {
  job_id: string;
  status: DataExportStatus;
  download_url?: string | null;
  download_url_expires_at?: string | null;
  created_at: string;
}

/** Response from POST /users/me/erasure-requests/request-erasure/ */
export interface RequestErasureResponse {
  request_id: string;
  status: ErasureRequestStatus;
  requested_at: string;
  completed_at?: string | null;
}
