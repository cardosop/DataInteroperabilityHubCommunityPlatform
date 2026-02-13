/**
 * File Types
 * Based on backend FileSerializer and File model
 */

export const FileStatus = {
  PENDING: 'PENDING',
  UPLOADING: 'UPLOADING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
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
