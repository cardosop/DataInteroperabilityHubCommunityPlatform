/**
 * File Types
 * Based on backend FileSerializer and File model
 */

export const FileStatus = {
  PENDING: 'PENDING',
  UPLOADING: 'UPLOADING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  ACTIVE: 'ACTIVE',
} as const;
export type FileStatus = (typeof FileStatus)[keyof typeof FileStatus];

export interface File {
  id: string;
  name: string;
  content_type: string;
  size: number;
  storage_path: string;
  status: FileStatus;
  content_sha256?: string;
  scan_status?: FileScanStatus;
  scanned_at?: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  tenant_id: string;
  asset_id?: string;
  dataset_id?: string;
  metadata_json?: Record<string, unknown>;
}

export interface FileInitRequest {
  name: string;
  content_type: string;
  size: number;
  upload_method?: 'browser' | 'sdk';
}

export interface FileInitResponse {
  file_id: string;
  upload_url: string;
  fields?: Record<string, string>;
  chunk_size?: number;
  chunk_count?: number;
  requires_multipart?: boolean;
  upload_id?: string;
}

export interface FileUploadProgress {
  file_id: string;
  uploaded: number;
  total: number;
  percentage: number;
  status: 'uploading' | 'completed' | 'failed';
  error?: string;
}

export interface FileCompleteRequest {
  file_id: string;
  content_sha256?: string;
  parts?: Array<{ ETag: string; PartNumber: number }>;
}

export const FileScanStatus = {
  CLEAN: 'CLEAN',
  INFECTED: 'INFECTED',
  SCANNING: 'SCANNING',
  UNKNOWN: 'UNKNOWN',
  PENDING_SCAN: 'PENDING_SCAN',
  SCAN_ERROR: 'SCAN_ERROR',
  SCAN_UNAVAILABLE: 'SCAN_UNAVAILABLE',
} as const;
export type FileScanStatus = (typeof FileScanStatus)[keyof typeof FileScanStatus];

export interface FileStorageQuota {
  used_bytes: number;
  total_bytes: number;
  file_count: number;
  unlimited?: boolean;
  limit_bytes?: number;
  percentage?: number;
}
