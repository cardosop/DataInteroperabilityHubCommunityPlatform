/**
 * File Service
 * API client for file operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  File,
  FileCompleteRequest,
  FileInitRequest,
  FileInitResponse,
} from '../../../shared/types/files';

const FILES_BASE_PATH = 'files';

export const fileService = {
  /**
   * Initialize file upload (get presigned URL)
   */
  async initUpload(data: FileInitRequest): Promise<FileInitResponse> {
    const response = await apiClient
      .getClient()
      .post<FileInitResponse>(`${FILES_BASE_PATH}/init/`, data);
    return response.data;
  },

  /**
   * Upload file to S3 using presigned URL
   */
  async uploadToS3(
    uploadUrl: string,
    file: Blob,
    onProgress?: (progress: number) => void
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const startTime = Date.now();

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable && onProgress) {
          const progress = (event.loaded / event.total) * 100;
          onProgress(progress);
        }
      });

      xhr.addEventListener('load', () => {
        const duration = Date.now() - startTime;
        if (xhr.status >= 200 && xhr.status < 300) {
          console.log(`File upload completed in ${duration}ms`);
          resolve();
        } else {
          console.error(`Upload failed with status ${xhr.status}`);
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      });

      xhr.addEventListener('error', (e) => {
        const duration = Date.now() - startTime;
        console.error(`Upload error after ${duration}ms:`, e);
        reject(new Error('Upload failed'));
      });

      xhr.addEventListener('abort', () => {
        reject(new Error('Upload aborted'));
      });

      xhr.addEventListener('timeout', () => {
        reject(new Error('Upload timeout'));
      });

      // Set timeout to 2 minutes for large files
      xhr.timeout = 120000;

      xhr.open('PUT', uploadUrl);
      xhr.setRequestHeader(
        'Content-Type',
        (file as Blob & { type?: string }).type || 'application/octet-stream'
      );
      xhr.send(file);
    });
  },

  /**
   * Calculate SHA-256 hash of a file
   */
  async calculateFileHash(file: Blob): Promise<string> {
    const arrayBuffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
    return hashHex;
  },

  /**
   * Complete file upload
   */
  async completeUpload(data: FileCompleteRequest): Promise<File> {
    const response = await apiClient
      .getClient()
      .post<File>(`${FILES_BASE_PATH}/${data.file_id}/complete/`, {
        content_sha256: data.content_sha256,
        parts: data.parts,
      });
    return response.data;
  },

  /**
   * Upload file with progress tracking
   * This is a convenience method that combines init, upload, and complete
   */
  async uploadFile(
    file: Blob,
    options: {
      name?: string;
      onProgress?: (progress: number) => void;
    } = {}
  ): Promise<File> {
    const fileName = options.name || (file instanceof globalThis.File ? file.name : 'upload');
    const fileSize = file.size;
    const contentType = (file as Blob & { type?: string }).type || 'application/octet-stream';

    // Step 1: Initialize upload
    const initResponse = await this.initUpload({
      name: fileName,
      content_type: contentType,
      size: fileSize,
      upload_method: 'browser',
    });

    // Step 2: Calculate SHA-256 hash (before upload to avoid reading file twice)
    const contentSha256 = await this.calculateFileHash(file);
    console.log(`[FileService] Calculated SHA-256: ${contentSha256.substring(0, 16)}...`);

    // Step 3: Upload to S3
    await this.uploadToS3(initResponse.upload_url, file, options.onProgress);

    // Step 4: Complete upload with hash
    const completedFile = await this.completeUpload({
      file_id: initResponse.file_id,
      content_sha256: contentSha256,
    });

    return completedFile;
  },

  /**
   * List files
   */
  async list(
    filters: {
      page?: number;
      page_size?: number;
      asset_id?: string;
      dataset_id?: string;
    } = {}
  ): Promise<PaginatedResponse<File>> {
    const params = new URLSearchParams();

    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.asset_id) params.append('asset_id', filters.asset_id);
    if (filters.dataset_id) params.append('dataset_id', filters.dataset_id);

    const url = params.toString()
      ? `${FILES_BASE_PATH}/?${params.toString()}`
      : `${FILES_BASE_PATH}/`;
    const response = await apiClient
      .getClient()
      .get<PaginatedResponse<File> & { next?: string | null; previous?: string | null }>(url);
    const data = response.data;
    if (
      typeof data.has_next !== 'boolean' &&
      (data.next !== undefined || data.previous !== undefined)
    ) {
      return {
        ...data,
        has_next: !!data.next,
        has_previous: !!data.previous,
        next_page: data.next != null ? data.page + 1 : null,
        previous_page: data.previous != null ? data.page - 1 : null,
      } as PaginatedResponse<File>;
    }
    return data as PaginatedResponse<File>;
  },

  /**
   * Get file by ID
   */
  async getById(id: string): Promise<File> {
    const response = await apiClient.getClient().get<File>(`${FILES_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Delete file
   */
  async delete(id: string): Promise<void> {
    await apiClient.getClient().delete(`${FILES_BASE_PATH}/${id}/`);
  },
};
