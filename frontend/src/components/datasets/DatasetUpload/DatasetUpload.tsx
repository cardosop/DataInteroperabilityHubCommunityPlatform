/**
 * Dataset Upload Component
 *
 * Reusable component for uploading dataset files.
 * Wraps FileUpload component with dataset-specific configuration and logic.
 */

import React, { useState, useCallback } from 'react'
import { FileUpload } from '@/components/forms/FileUpload'
import { useUploadDataset } from '@/hooks/useDatasets'
import type { Dataset } from '@/lib/api/datasets'

/**
 * Valid file types for dataset upload
 */
const VALID_FILE_TYPES = ['.csv', '.json', '.parquet']
const VALID_MIME_TYPES = [
  'text/csv',
  'application/json',
  'application/parquet',
  'application/x-parquet',
]

/**
 * Maximum file size: 500MB
 */
const MAX_FILE_SIZE = 500 * 1024 * 1024

/**
 * Validate file type and size
 */
const validateFile = (file: File): string | null => {
  // Check file extension
  const extension = '.' + file.name.split('.').pop()?.toLowerCase()
  const isValidExtension = VALID_FILE_TYPES.includes(extension)
  const isValidMimeType = VALID_MIME_TYPES.includes(file.type)

  if (!isValidExtension && !isValidMimeType) {
    return `Invalid file type. Supported formats: CSV, JSON, Parquet`
  }

  // Check file size
  if (file.size > MAX_FILE_SIZE) {
    return `File size exceeds maximum limit of ${(MAX_FILE_SIZE / 1024 / 1024).toFixed(0)}MB`
  }

  return null
}

export interface DatasetUploadProps {
  /**
   * Callback when upload succeeds
   */
  onUploadSuccess: (dataset: Dataset) => void
  /**
   * Callback when upload fails
   */
  onUploadError?: (error: Error) => void
  /**
   * Asset ID to attach dataset to (optional)
   */
  asset_id?: string | null
  /**
   * Whether upload is disabled
   * @default false
   */
  disabled?: boolean
  /**
   * Additional className
   */
  className?: string
}

/**
 * Dataset Upload Component
 *
 * Reusable component for uploading dataset files with validation and progress tracking.
 *
 * @example
 * ```tsx
 * <DatasetUpload
 *   onUploadSuccess={(dataset) => {
 *     console.log('Uploaded:', dataset)
 *     navigate(`/datasets/${dataset.id}`)
 *   }}
 *   onUploadError={(error) => {
 *     console.error('Upload failed:', error)
 *   }}
 *   asset_id="asset-123"
 * />
 * ```
 */
export const DatasetUpload: React.FC<DatasetUploadProps> = ({
  onUploadSuccess,
  onUploadError,
  asset_id = null,
  disabled = false,
  className,
}) => {
  const uploadDataset = useUploadDataset()
  const [uploadProgress, setUploadProgress] = useState<number | undefined>(undefined)
  const [uploadError, setUploadError] = useState<string | null>(null)

  // Handle file upload
  const handleUpload = useCallback(
    async (file: File) => {
      // Validate file
      const validationError = validateFile(file)
      if (validationError) {
        setUploadError(validationError)
        setUploadProgress(undefined)
        if (onUploadError) {
          onUploadError(new Error(validationError))
        }
        return
      }

      // Clear previous errors
      setUploadError(null)
      setUploadProgress(0)

      try {
        // Upload dataset with progress tracking
        const dataset = await uploadDataset.mutateAsync({
          file,
          asset_id: asset_id || null,
          onProgress: (progress) => {
            setUploadProgress(progress)
          },
        })

        setUploadProgress(100)
        onUploadSuccess(dataset)
      } catch (error) {
        console.error('Dataset upload failed:', error)
        const errorMessage =
          error instanceof Error ? error.message : 'Failed to upload dataset. Please try again.'
        setUploadError(errorMessage)
        setUploadProgress(undefined)
        if (onUploadError) {
          onUploadError(error instanceof Error ? error : new Error(errorMessage))
        }
      }
    },
    [uploadDataset, asset_id, onUploadSuccess, onUploadError]
  )

  // Check if upload is in progress
  const isUploading = uploadDataset.isPending || (uploadProgress !== undefined && uploadProgress < 100)

  return (
    <FileUpload
      accept=".csv,.json,.parquet"
      maxSize={MAX_FILE_SIZE}
      onUpload={handleUpload}
      progress={uploadProgress}
      error={uploadError}
      disabled={disabled || isUploading}
      className={className}
    />
  )
}

DatasetUpload.displayName = 'DatasetUpload'

