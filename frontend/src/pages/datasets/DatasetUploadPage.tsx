/**
 * Dataset Upload Page
 *
 * Comprehensive dataset upload page with:
 * - File upload component with drag-and-drop support
 * - File validation (type and size)
 * - Upload progress tracking
 * - Success/error handling
 * - Navigation to dataset detail on success
 */

import React, { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Container,
  Box,
  Typography,
  Paper,
  Alert,
  Button,
} from '@mui/material'
import {
  CheckCircle as CheckCircleIcon,
  ArrowBack as ArrowBackIcon,
  Description as DescriptionIcon,
} from '@mui/icons-material'
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
 * Format file size for display
 */
const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

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
    return `File size exceeds maximum limit of ${formatFileSize(MAX_FILE_SIZE)}`
  }

  return null
}

/**
 * Dataset Upload Page Component
 */
export const DatasetUploadPage: React.FC = () => {
  const navigate = useNavigate()
  const uploadDataset = useUploadDataset()

  // State
  const [uploadProgress, setUploadProgress] = useState<number | undefined>(undefined)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [uploadedDataset, setUploadedDataset] = useState<Dataset | null>(null)

  // Handle file upload
  const handleUpload = useCallback(
    async (file: File) => {
      // Validate file
      const validationError = validateFile(file)
      if (validationError) {
        setUploadError(validationError)
        setUploadProgress(undefined)
        return
      }

      // Clear previous errors
      setUploadError(null)
      setUploadProgress(0)
      setUploadedFile(file)
      setUploadedDataset(null)

      try {
        // Upload dataset with progress tracking
        const dataset = await uploadDataset.mutateAsync({
          file,
          asset_id: null, // Optional: can be added later if needed
          onProgress: (progress) => {
            setUploadProgress(progress)
          },
        })

        // Store uploaded dataset
        setUploadedDataset(dataset)
        setUploadProgress(100)

        // Navigate to dataset detail page after a short delay to show success
        setTimeout(() => {
          navigate(`/datasets/${dataset.id}`)
        }, 1500)
      } catch (error) {
        console.error('Dataset upload failed:', error)
        setUploadError(
          error instanceof Error
            ? error.message
            : 'Failed to upload dataset. Please try again.'
        )
        setUploadProgress(undefined)
        setUploadedFile(null)
      }
    },
    [uploadDataset, navigate]
  )

  // Handle file removal
  const handleRemoveFile = useCallback(() => {
    setUploadedFile(null)
    setUploadedDataset(null)
    setUploadError(null)
    setUploadProgress(undefined)
  }, [])

  // Handle retry
  const handleRetry = useCallback(() => {
    if (uploadedFile) {
      handleUpload(uploadedFile)
    }
  }, [uploadedFile, handleUpload])

  // Check if upload is in progress
  const isUploading = uploadDataset.isPending || (uploadProgress !== undefined && uploadProgress < 100)

  return (
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4 }}>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/datasets')}
            sx={{ mb: 2 }}
          >
            Back to Datasets
          </Button>
          <Typography variant="h4" gutterBottom>
            Upload Dataset
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Upload a dataset file to create a new dataset. Supported formats: CSV, JSON, Parquet
          </Typography>
        </Box>

        {/* File Upload Zone */}
        {!uploadedDataset && (
          <Paper sx={{ p: 4, mb: 3 }}>
            <FileUpload
              accept=".csv,.json,.parquet"
              maxSize={MAX_FILE_SIZE}
              onUpload={handleUpload}
              progress={uploadProgress}
              error={uploadError}
              disabled={isUploading}
            />
          </Paper>
        )}

        {/* Uploaded File Info */}
        {uploadedFile && !isUploading && !uploadedDataset && (
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <DescriptionIcon sx={{ fontSize: 40, color: 'text.secondary' }} />
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
                onClick={handleRemoveFile}
                disabled={isUploading}
              >
                Remove
              </Button>
            </Box>
          </Paper>
        )}

        {/* Success State */}
        {uploadedDataset && (
          <Paper
            sx={{
              p: 4,
              mb: 3,
              backgroundColor: 'success.50',
              border: '1px solid',
              borderColor: 'success.200',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
              <CheckCircleIcon sx={{ fontSize: 40, color: 'success.main' }} />
              <Box sx={{ flex: 1 }}>
                <Typography variant="h6" gutterBottom>
                  Dataset Uploaded Successfully!
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Your dataset has been uploaded and is being processed. Redirecting to dataset
                  details...
                </Typography>
              </Box>
            </Box>
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button
                variant="contained"
                onClick={() => navigate(`/datasets/${uploadedDataset.id}`)}
              >
                View Dataset
              </Button>
              <Button
                variant="outlined"
                onClick={() => {
                  handleRemoveFile()
                  navigate('/datasets')
                }}
              >
                Upload Another
              </Button>
            </Box>
          </Paper>
        )}

        {/* Error Alert */}
        {uploadError && !uploadedDataset && (
          <Alert
            severity="error"
            sx={{ mb: 3 }}
            action={
              uploadedFile && (
                <Button color="inherit" size="small" onClick={handleRetry}>
                  Retry
                </Button>
              )
            }
          >
            <Typography variant="body2" fontWeight={500} gutterBottom>
              Upload Failed
            </Typography>
            <Typography variant="body2">{uploadError}</Typography>
          </Alert>
        )}

        {/* Upload Info */}
        <Paper sx={{ p: 3, mt: 4, backgroundColor: 'info.50' }}>
          <Typography variant="subtitle2" fontWeight={500} gutterBottom>
            What happens after upload?
          </Typography>
          <Box component="ul" sx={{ m: 0, pl: 3 }}>
            <li>
              <Typography variant="body2" color="text.secondary">
                File is uploaded to secure storage
              </Typography>
            </li>
            <li>
              <Typography variant="body2" color="text.secondary">
                Schema is automatically inferred from your data
              </Typography>
            </li>
            <li>
              <Typography variant="body2" color="text.secondary">
                Data quality checks are run
              </Typography>
            </li>
            <li>
              <Typography variant="body2" color="text.secondary">
                Dataset is created and ready for use
              </Typography>
            </li>
          </Box>
        </Paper>
      </Box>
    </Container>
  )
}

