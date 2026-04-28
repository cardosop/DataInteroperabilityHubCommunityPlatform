/**
 * File Upload Component
 * Handles file upload with progress tracking
 */

import { useState, useRef, useEffect } from 'react';
import { useUploadFile } from '../hooks/useFiles';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import type { File as AppFile } from '../../../shared/types/files';
import './FileUpload.css';

interface FileUploadProps {
  onUploadComplete?: (file: AppFile) => void;
  onUploadError?: (error: Error) => void;
  assetId?: string;
  datasetId?: string;
  accept?: string;
}

export function FileUpload({
  onUploadComplete,
  onUploadError,
  accept = '.csv,.json,.parquet',
}: FileUploadProps) {
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const successTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const uploadMutation = useUploadFile();

  // Clean up success timer on unmount
  useEffect(() => {
    return () => clearTimeout(successTimerRef.current);
  }, []);

  const handleFileSelect = async (file: globalThis.File) => {
    setUploadProgress(0);
    setUploadSuccess(false);
    const startTime = Date.now();
    console.log(`[FileUpload] Starting upload: ${file.name} (${file.size} bytes)`);
    
    try {
      const uploadedFile = await uploadMutation.mutateAsync({
        file,
        options: {
          onProgress: (progress) => {
            setUploadProgress(progress);
            if (progress > 0 && progress < 100) {
              console.log(`[FileUpload] Progress: ${Math.round(progress)}%`);
            }
          },
        },
      });
      const duration = Date.now() - startTime;
      console.log(`[FileUpload] Upload completed in ${duration}ms: ${uploadedFile.id}`);
      setUploadProgress(100);
      setUploadSuccess(true);
      onUploadComplete?.(uploadedFile as AppFile);
      
      // Reset success state after 10 seconds to show dropzone again (longer for tests to detect)
      clearTimeout(successTimerRef.current);
      successTimerRef.current = setTimeout(() => {
        setUploadSuccess(false);
        setUploadProgress(null);
      }, 10000);
    } catch (error) {
      const duration = Date.now() - startTime;
      const err = error instanceof Error ? error : new Error('Upload failed');
      console.error(`[FileUpload] Upload failed after ${duration}ms:`, err);
      onUploadError?.(err);
      setUploadProgress(null);
      setUploadSuccess(false);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  const isUploading = uploadMutation.isPending || (uploadProgress !== null && uploadProgress < 100);
  const showSuccess = uploadSuccess && uploadProgress === 100;

  return (
    // Phase 226.F1.b — data-testid on the wrapper + dropzone for stable
    // e2e selectors. The dropzone testid carries the upload state in a
    // suffix-free attribute so specs don't have to parse the className
    // template (`getByTestId('file-upload-dropzone')` works regardless
    // of dragging/uploading/success state).
    <div className="file-upload" data-testid="file-upload">
      <div
        className={`file-upload-dropzone ${isDragging ? 'dragging' : ''} ${isUploading ? 'uploading' : ''} ${showSuccess ? 'upload-success' : ''}`}
        data-testid="file-upload-dropzone"
        data-upload-state={
          showSuccess ? 'success' : isUploading ? 'uploading' : isDragging ? 'dragging' : 'idle'
        }
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={handleClick}
        role="button"
        tabIndex={0}
        aria-label="Upload file"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={accept}
          onChange={handleFileInputChange}
          className="file-upload-input"
          aria-label="File input"
        />
        {showSuccess ? (
          <div className="file-upload-success">
            <div className="file-upload-success-icon">✅</div>
            <p className="file-upload-success-text">File uploaded successfully!</p>
          </div>
        ) : isUploading ? (
          <div className="file-upload-progress">
            <LoadingSpinner size="small" />
            <p>Uploading... {uploadProgress !== null ? `${Math.round(uploadProgress)}%` : ''}</p>
            {uploadProgress !== null && (
              <div className="file-upload-progress-bar">
                <div
                  className="file-upload-progress-fill"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            )}
          </div>
        ) : (
          <div className="file-upload-content">
            <div className="file-upload-icon">📁</div>
            <p className="file-upload-text">
              Drag and drop a file here, or click to select
            </p>
            <p className="file-upload-hint">
              Supported formats: CSV, JSON, Parquet
            </p>
          </div>
        )}
      </div>
      {uploadMutation.isError && (
        <ErrorDisplay
          error={uploadMutation.error}
          title="Upload failed"
          onRetry={() => uploadMutation.reset()}
        />
      )}
    </div>
  );
}
