/**
 * File Upload Step
 *
 * Step 2 (Data-First) or Step 3 (Contract-First): File upload
 * Implements UI-DPO-002: File Upload
 */

import React, { useState, useCallback } from 'react'
import { Box, Typography, Paper, Alert, Button } from '@mui/material'
import {
  CloudUpload as CloudUploadIcon,
  CheckCircle as CheckCircleIcon,
  Description as DescriptionIcon,
} from '@mui/icons-material'
import { FileUpload } from '@/components/forms/FileUpload'
import { uploadDataset } from '@/lib/api/datasets'
import type { AssetFormData } from '../AssetFormPage'

export interface FileUploadStepProps {
  formData: AssetFormData
  onUpdate: (updates: Partial<AssetFormData>) => void
  onCreateAsset: () => Promise<string>
  isContractFirst?: boolean
}

/**
 * File Upload Step Component
 */
export const FileUploadStep: React.FC<FileUploadStepProps> = ({
  formData,
  onUpdate,
  onCreateAsset,
  isContractFirst = false,
}) => {
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadedFile, setUploadedFile] = useState<File | null>(
    formData.uploadedFile || null
  )

  // Validate file type
  const validateFile = useCallback((file: File): string | null => {
    const validTypes = ['.csv', '.json', '.parquet']
    const validMimeTypes = [
      'text/csv',
      'application/json',
      'application/parquet',
      'application/x-parquet',
    ]

    const extension = '.' + file.name.split('.').pop()?.toLowerCase()
    const isValidExtension = validTypes.includes(extension)
    const isValidMimeType = validMimeTypes.includes(file.type)

    if (!isValidExtension && !isValidMimeType) {
      return `Invalid file type. Supported formats: CSV, JSON, Parquet`
    }

    // Check file size (max 500MB)
    const maxSize = 500 * 1024 * 1024 // 500MB
    if (file.size > maxSize) {
      return `File size exceeds maximum limit of 500MB`
    }

    return null
  }, [])

  // Handle file upload
  const handleUpload = useCallback(
    async (file: File) => {
      const validationError = validateFile(file)
      if (validationError) {
        setUploadError(validationError)
        return
      }

      setUploadError(null)
      setUploading(true)
      setUploadProgress(0)
      setUploadedFile(file)

      try {
        // Create asset if not already created
        let assetId = formData.workflowInstanceId
        if (!assetId) {
          assetId = await onCreateAsset()
          onUpdate({ workflowInstanceId: assetId })
        }

        // Upload dataset
        const dataset = await uploadDataset(
          {
            file,
            asset_id: assetId,
            onProgress: (progress) => {
              setUploadProgress(progress)
            },
          }
        )

        onUpdate({
          fileId: dataset.file,
          datasetId: dataset.id,
          uploadedFile: file,
        })

        setUploadProgress(100)
      } catch (error) {
        console.error('File upload failed:', error)
        setUploadError(
          error instanceof Error
            ? error.message
            : 'Failed to upload file. Please try again.'
        )
        setUploadedFile(null)
      } finally {
        setUploading(false)
      }
    },
    [formData.workflowInstanceId, validateFile, onCreateAsset, onUpdate]
  )

  // Format file size
  const formatFileSize = useCallback((bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
  }, [])

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        {isContractFirst ? 'Upload Dataset File' : 'Upload Data File'}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
        {isContractFirst
          ? 'Upload a dataset file to attach to your contract'
          : 'Upload your data file. We will analyze it and create a contract for you.'}
      </Typography>

      {/* File Upload Zone */}
      {!uploadedFile && (
        <FileUpload
          accept=".csv,.json,.parquet"
          maxSize={500 * 1024 * 1024} // 500MB
          onUpload={handleUpload}
          progress={uploading ? uploadProgress : undefined}
          error={uploadError}
          disabled={uploading}
        />
      )}

      {/* Uploaded File Info */}
      {uploadedFile && !uploading && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <CheckCircleIcon color="success" />
            <Box sx={{ flex: 1 }}>
              <Typography variant="subtitle1" fontWeight={500}>
                {uploadedFile.name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {formatFileSize(uploadedFile.size)} • {uploadedFile.type || 'Unknown type'}
              </Typography>
            </Box>
            <Button
              variant="outlined"
              size="small"
              onClick={() => {
                setUploadedFile(null)
                onUpdate({ uploadedFile: undefined, fileId: undefined, datasetId: undefined })
              }}
            >
              Remove
            </Button>
          </Box>
        </Paper>
      )}

      {/* Error Alert */}
      {uploadError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {uploadError}
        </Alert>
      )}

      {/* What happens next? */}
      {!isContractFirst && (
        <Paper sx={{ p: 3, mt: 4, backgroundColor: 'info.50' }}>
          <Typography variant="subtitle2" fontWeight={500} gutterBottom>
            What happens next?
          </Typography>
          <Box component="ul" sx={{ m: 0, pl: 3 }}>
            <li>File is uploaded to secure storage</li>
            <li>Schema is automatically inferred from your data</li>
            <li>Data quality checks are run</li>
            <li>Compliance checks are performed</li>
            <li>You review and edit the generated contract</li>
          </Box>
        </Paper>
      )}
    </Box>
  )
}

