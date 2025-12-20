import React, { useRef, useState, DragEvent } from 'react'
import { cn, useId } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'
import { ProgressBar } from '@/components/feedback/ProgressBar'

export interface FileUploadProps {
  /**
   * Accepted file types (e.g., ".pdf,.doc,.docx")
   */
  accept?: string
  /**
   * Maximum file size in bytes
   */
  maxSize?: number
  /**
   * Callback when file is uploaded
   */
  onUpload: (file: File) => void | Promise<void>
  /**
   * Whether multiple files are allowed
   * @default false
   */
  multiple?: boolean
  /**
   * Upload progress (0-100)
   */
  progress?: number
  /**
   * Error message
   */
  error?: string | null
  /**
   * Whether upload is disabled
   */
  disabled?: boolean
  className?: string
}

/**
 * FileUpload component with drag-and-drop support
 */
export const FileUpload: React.FC<FileUploadProps> = ({
  accept,
  maxSize,
  onUpload,
  multiple = false,
  progress,
  error,
  disabled,
  className,
}) => {
  const fileInputId = useId('file-upload')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)

  const validateFile = (file: File): string | null => {
    if (maxSize && file.size > maxSize) {
      return `File size exceeds maximum limit of ${(maxSize / 1024 / 1024).toFixed(2)}MB`
    }
    if (accept) {
      const acceptedTypes = accept.split(',').map((t) => t.trim())
      const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase()
      if (!acceptedTypes.includes(fileExtension) && !acceptedTypes.includes(file.type)) {
        return `File type not accepted. Accepted types: ${accept}`
      }
    }
    return null
  }

  const handleFile = async (file: File) => {
    const validationError = validateFile(file)
    if (validationError) {
      // In a real app, you'd show this error to the user
      console.error(validationError)
      return
    }

    setUploading(true)
    try {
      await onUpload(file)
    } finally {
      setUploading(false)
    }
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)

    if (disabled || uploading) return

    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) {
      handleFile(files[0])
    }
  }

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    if (!disabled && !uploading) {
      setIsDragging(true)
    }
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      handleFile(files[0])
    }
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  return (
    <div className={cn('file-upload', className)}>
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !disabled && !uploading && fileInputRef.current?.click()}
        style={{
          minHeight: '200px',
          border: `2px dashed ${
            error
              ? colors.error[500]
              : isDragging
                ? colors.primary[500]
                : colors.semantic.borderDefault
          }`,
          borderRadius: borderRadius.md,
          padding: spacing[6],
          background: isDragging
            ? colors.primary[50]
            : colors.semantic.backgroundPaper,
          cursor: disabled || uploading ? 'not-allowed' : 'pointer',
          transition: 'all 0.2s',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: spacing[3],
          opacity: disabled ? 0.5 : 1,
        }}
      >
        <input
          ref={fileInputRef}
          id={fileInputId}
          type="file"
          accept={accept}
          multiple={multiple}
          disabled={disabled || uploading}
          onChange={handleFileInputChange}
          style={{ display: 'none' }}
        />
        <div
          style={{
            fontSize: '48px',
            color: colors.semantic.textSecondary,
          }}
        >
          📁
        </div>
        <div
          style={{
            textAlign: 'center',
            color: colors.semantic.textPrimary,
            fontSize: '16px',
            fontWeight: 500,
          }}
        >
          {uploading ? 'Uploading...' : 'Drag and drop a file here'}
        </div>
        <div
          style={{
            textAlign: 'center',
            color: colors.semantic.textSecondary,
            fontSize: '14px',
          }}
        >
          or click to browse
        </div>
        {accept && (
          <div
            style={{
              fontSize: '12px',
              color: colors.semantic.textHint,
            }}
          >
            Accepted: {accept}
          </div>
        )}
        {maxSize && (
          <div
            style={{
              fontSize: '12px',
              color: colors.semantic.textHint,
            }}
          >
            Max size: {formatFileSize(maxSize)}
          </div>
        )}
      </div>
      {progress !== undefined && (
        <div style={{ marginTop: spacing[2] }}>
          <ProgressBar value={progress} showValue />
        </div>
      )}
      {error && (
        <div
          role="alert"
          style={{
            marginTop: spacing[2],
            fontSize: '12px',
            color: colors.error[500],
          }}
        >
          {error}
        </div>
      )}
    </div>
  )
}

FileUpload.displayName = 'FileUpload'

