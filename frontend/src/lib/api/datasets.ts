/**
 * Dataset API Service
 *
 * API functions for dataset management operations:
 * - List datasets with filtering, sorting, and pagination
 * - Get single dataset by ID
 * - Create dataset from file
 * - Upload file and create dataset (combined operation)
 */

import type { ExtendedFetchRequestInit } from 'axios'
import { apiClient } from './client'
import { PaginatedResponse } from './responses'

/**
 * Dataset format enum
 */
export type DatasetFormat = 'CSV' | 'JSON' | 'PARQUET'

/**
 * Schema field definition
 */
export interface SchemaField {
  name: string
  type: string
  nullable: boolean
}

/**
 * Dataset schema
 */
export interface DatasetSchema {
  fields: SchemaField[]
}

/**
 * Dataset model
 */
export interface Dataset {
  id: string
  tenant: string
  asset: string | null
  file: string
  schema_json: DatasetSchema | null
  sample_data_json: any[] | null
  row_count: number | null
  format: DatasetFormat
  version: number
  parent_version: string | null
  semantic_version: string | null
  version_tags: string[]
  is_current: boolean
  created_by: string
  created_at: string
  updated_at: string
}

/**
 * List datasets query parameters
 */
export interface ListDatasetsParams {
  /**
   * Page number (1-indexed)
   */
  page?: number
  /**
   * Number of items per page (default: 50, max: 100)
   */
  page_size?: number
  /**
   * Sort fields (comma-separated, prefix with `-` for descending)
   * Example: "created_at,-version"
   */
  ordering?: string
  /**
   * Search in dataset metadata
   */
  search?: string
  /**
   * Filter by asset ID
   */
  asset_id?: string
  /**
   * Filter by format (CSV, JSON, PARQUET)
   */
  format?: DatasetFormat
}

/**
 * Create dataset request payload
 */
export interface CreateDatasetRequest {
  /**
   * ID of the file to create dataset from (required)
   */
  file_id: string
  /**
   * ID of the asset to attach dataset to (optional)
   */
  asset_id?: string | null
}

/**
 * File upload initialization request
 */
export interface FileUploadInitRequest {
  /**
   * Original filename (required, max 255 chars)
   */
  name: string
  /**
   * MIME type (required, max 100 chars)
   */
  content_type: string
  /**
   * File size in bytes (required, min 0)
   */
  size: number
  /**
   * Upload method: browser or sdk (optional, default: browser)
   */
  upload_method?: 'browser' | 'sdk'
}

/**
 * File upload initialization response
 */
export interface FileUploadInitResponse {
  /**
   * File ID for the upload
   */
  file_id: string
  /**
   * Pre-signed URL for direct S3 upload
   */
  upload_url: string
  /**
   * Form fields for POST request (if using form upload)
   */
  fields: Record<string, string>
  /**
   * Recommended chunk size for multipart upload (optional)
   */
  chunk_size?: number
  /**
   * Number of chunks for multipart upload (optional)
   */
  chunk_count?: number
  /**
   * Whether multipart upload is required
   */
  requires_multipart: boolean
}

/**
 * File upload completion request
 */
export interface FileUploadCompleteRequest {
  /**
   * SHA-256 hash of uploaded file content (for verification)
   */
  content_sha256: string
  /**
   * List of parts for multipart upload (ETag and PartNumber) (optional)
   */
  parts?: Array<{
    etag: string
    part_number: number
  }>
}

/**
 * File upload completion response
 */
export interface FileUploadCompleteResponse {
  /**
   * File ID
   */
  id: string
  /**
   * File name
   */
  name: string
  /**
   * File status
   */
  status: string
}

/**
 * Upload dataset request (combines file upload and dataset creation)
 */
export interface UploadDatasetRequest {
  /**
   * File to upload
   */
  file: File
  /**
   * ID of the asset to attach dataset to (optional)
   */
  asset_id?: string | null
  /**
   * Optional callback for upload progress (0-100)
   */
  onProgress?: (progress: number) => void
}

/**
 * List datasets response
 */
export type ListDatasetsResponse = PaginatedResponse<Dataset>

/**
 * Dataset version (for version history)
 */
export interface DatasetVersion {
  id: string
  version: number
  semantic_version: string | null
  version_tags: string[]
  is_current: boolean
  created_at: string
  updated_at: string
}

/**
 * Get dataset by ID
 *
 * @param id - Dataset UUID
 * @param config - Optional Axios request config
 * @returns Dataset details
 */
export async function getDataset(
  id: string,
  config?: ExtendedFetchRequestInit
): Promise<Dataset> {
  const response = await apiClient.get<Dataset>(`/api/v1/datasets/${id}/`, config)
  return response.data
}

/**
 * Get dataset versions
 *
 * @param id - Dataset UUID
 * @param config - Optional Axios request config
 * @returns List of dataset versions
 */
export async function getDatasetVersions(
  id: string,
  config?: ExtendedFetchRequestInit
): Promise<DatasetVersion[]> {
  const response = await apiClient.get<DatasetVersion[]>(
    `/api/v1/datasets/${id}/versions/`,
    config
  )
  return response.data
}

/**
 * Get file download URL
 *
 * @param fileId - File UUID
 * @param config - Optional Axios request config
 * @returns Download URL response
 */
export interface FileDownloadResponse {
  download_url: string
  expires_in: number
  filename: string
}

export async function getFileDownloadUrl(
  fileId: string,
  config?: ExtendedFetchRequestInit
): Promise<FileDownloadResponse> {
  // Note: The endpoint is GET according to the views.py implementation
  const response = await apiClient.get<FileDownloadResponse>(
    `/api/v1/files/${fileId}/download/`,
    config
  )
  return response.data
}

/**
 * List datasets with filtering, sorting, and pagination
 *
 * @param params - Query parameters for filtering and pagination
 * @param requestConfig - Optional Axios request config
 * @returns Paginated list of datasets
 */
export async function listDatasets(
  params?: ListDatasetsParams,
  requestConfig?: ExtendedFetchRequestInit
): Promise<ListDatasetsResponse> {
  const response = await apiClient.get<ListDatasetsResponse>(
    '/api/v1/datasets/',
    {
      ...requestConfig,
      params: {
        page: params?.page,
        page_size: params?.page_size,
        ordering: params?.ordering,
        search: params?.search,
        asset_id: params?.asset_id,
        format: params?.format,
      },
    }
  )
  return response.data
}

/**
 * Create dataset from uploaded file
 *
 * @param data - Dataset creation data
 * @param requestConfig - Optional Axios request config
 * @returns Created dataset
 */
export async function createDataset(
  data: CreateDatasetRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<Dataset> {
  const response = await apiClient.post<Dataset>(
    '/api/v1/datasets/',
    data,
    requestConfig
  )
  return response.data
}

/**
 * Initialize file upload
 *
 * @param data - File upload initialization data
 * @param config - Optional Axios request config
 * @returns Upload initialization response with pre-signed URL
 */
export async function initFileUpload(
  data: FileUploadInitRequest,
  config?: ExtendedFetchRequestInit
): Promise<FileUploadInitResponse> {
  const response = await apiClient.post<FileUploadInitResponse>(
    '/api/v1/files/init/',
    data,
    config
  )
  return response.data
}

/**
 * Complete file upload
 *
 * @param fileId - File ID from upload initialization
 * @param data - Upload completion data
 * @param config - Optional Axios request config
 * @returns File upload completion response
 */
export async function completeFileUpload(
  fileId: string,
  data: FileUploadCompleteRequest,
  config?: ExtendedFetchRequestInit
): Promise<FileUploadCompleteResponse> {
  const response = await apiClient.post<FileUploadCompleteResponse>(
    `/api/v1/files/${fileId}/complete/`,
    data,
    config
  )
  return response.data
}

/**
 * Calculate SHA-256 hash of file content
 *
 * @param file - File to hash
 * @returns Promise resolving to hex hash string
 */
async function calculateFileHash(file: File): Promise<string> {
  const arrayBuffer = await file.arrayBuffer()
  const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  const hashHex = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('')
  return hashHex
}

/**
 * Upload file to S3 using pre-signed URL
 *
 * @param file - File to upload
 * @param uploadUrl - Pre-signed URL from initFileUpload
 * @param fields - Form fields from initFileUpload (if using form upload)
 * @param onProgress - Optional progress callback (0-100)
 * @returns Promise that resolves when upload is complete
 */
async function uploadFileToS3(
  file: File,
  uploadUrl: string,
  fields: Record<string, string>,
  onProgress?: (progress: number) => void
): Promise<void> {
  // Check if we need to use form upload or direct PUT
  if (Object.keys(fields).length > 0) {
    // Form-based upload (POST with multipart/form-data)
    const formData = new FormData()

    // Add all fields from the response
    Object.entries(fields).forEach(([key, value]) => {
      formData.append(key, value)
    })

    // Add the file (must be last)
    formData.append('file', file)

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()

      // Track upload progress
      if (onProgress) {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const progress = Math.round((e.loaded / e.total) * 100)
            onProgress(progress)
          }
        })
      }

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve()
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}`))
        }
      })

      xhr.addEventListener('error', () => {
        reject(new Error('Upload failed'))
      })

      xhr.open('POST', uploadUrl)
      xhr.send(formData)
    })
  } else {
    // Direct PUT upload
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()

      // Track upload progress
      if (onProgress) {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const progress = Math.round((e.loaded / e.total) * 100)
            onProgress(progress)
          }
        })
      }

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve()
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}`))
        }
      })

      xhr.addEventListener('error', () => {
        reject(new Error('Upload failed'))
      })

      xhr.open('PUT', uploadUrl)
      xhr.setRequestHeader('Content-Type', 'application/octet-stream')
      xhr.send(file)
    })
  }
}

/**
 * Upload dataset (combines file upload and dataset creation)
 *
 * This function handles the complete flow:
 * 1. Initialize file upload
 * 2. Upload file to S3
 * 3. Complete file upload
 * 4. Create dataset from uploaded file
 *
 * @param data - Upload dataset request
 * @param requestConfig - Optional Axios request config
 * @returns Created dataset
 */
export async function uploadDataset(
  data: UploadDatasetRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<Dataset> {
  const { file, asset_id, onProgress } = data

  // Step 1: Initialize file upload
  const initResponse = await initFileUpload(
    {
      name: file.name,
      content_type: file.type || 'application/octet-stream',
      size: file.size,
      upload_method: 'browser',
    },
    requestConfig
  )

  // Step 2: Upload file to S3
  if (onProgress) {
    onProgress(10) // 10% after init
  }

  await uploadFileToS3(file, initResponse.upload_url, initResponse.fields, (progress) => {
    // Map upload progress (0-100) to overall progress (10-80%)
    if (onProgress) {
      onProgress(10 + Math.round(progress * 0.7))
    }
  })

  if (onProgress) {
    onProgress(80) // 80% after upload
  }

  // Step 3: Complete file upload
  const fileHash = await calculateFileHash(file)
  await completeFileUpload(
    initResponse.file_id,
    {
      content_sha256: fileHash,
      parts: [], // Empty for non-multipart uploads
    },
    requestConfig
  )

  if (onProgress) {
    onProgress(90) // 90% after complete
  }

  // Step 4: Create dataset from uploaded file
  const dataset = await createDataset(
    {
      file_id: initResponse.file_id,
      asset_id: asset_id || null,
    },
    requestConfig
  )

  if (onProgress) {
    onProgress(100) // 100% after dataset creation
  }

  return dataset
}
