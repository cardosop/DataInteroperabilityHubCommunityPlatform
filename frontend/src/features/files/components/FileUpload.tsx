/**
 * File Upload Component
 * Handles file upload with progress tracking
 */

import { useState, useRef, useEffect } from 'react';
import { useMultipartUpload } from '../hooks/useMultipartUpload';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useToast } from '../../../shared/components/Toast';
import { getErrorMessage } from '../../../shared/utils/errorUtils';
import type { File as AppFile } from '../../../shared/types/files';
import {
  clearUploadCheckpoint,
  listResumableUploads,
  type UploadCheckpoint,
} from '../utils/multipartResumeStorage';
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
  // Phase 260.3.F — resumable-upload checkpoints (real localStorage
  // through multipartResumeStorage; listed once on mount, sorted
  // newest-first by the storage util).
  const [checkpoints, setCheckpoints] = useState<UploadCheckpoint[]>([]);
  // Phase 260.3.F.3 — resume CTA routing. When set, the NEXT file picked
  // through the shared input resumes that checkpoint instead of starting
  // a fresh upload. Cleared on any fresh-upload gesture (dropzone click /
  // drop / discard) so a canceled picker can't mis-route a later pick.
  const [pendingResumeFingerprint, setPendingResumeFingerprint] = useState<
    string | null
  >(null);
  const [resumeMismatchError, setResumeMismatchError] = useState<string | null>(
    null,
  );
  const fileInputRef = useRef<HTMLInputElement>(null);
  const successTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const resumeUpload = useMultipartUpload();
  // Success/error toasts were historically fired by
  // ``useMutationWithNotification`` (removed when uploads moved to the
  // MultipartUploader engine) — restore them here so every consumer
  // keeps the same user-visible feedback surface.
  const toast = useToast();

  useEffect(() => {
    setCheckpoints(listResumableUploads());
  }, []);

  // Clean up success timer on unmount
  useEffect(() => {
    return () => clearTimeout(successTimerRef.current);
  }, []);

  const handleDiscardCheckpoint = (fingerprint: string) => {
    clearUploadCheckpoint(fingerprint);
    setCheckpoints((current) =>
      current.filter((entry) => entry.fingerprint !== fingerprint),
    );
    if (pendingResumeFingerprint === fingerprint) {
      setPendingResumeFingerprint(null);
    }
    setResumeMismatchError(null);
  };

  const handleResumeClick = (fingerprint: string) => {
    // Phase 260.3.F.3 — the resume CTA opens the file picker (user
    // gesture) so the user can re-pick the same file whose upload was
    // interrupted. The next selection routes through the resume path.
    setPendingResumeFingerprint(fingerprint);
    setResumeMismatchError(null);
    fileInputRef.current?.click();
  };

  const finishSuccess = (uploaded: { id: string }) => {
    setUploadProgress(100);
    setUploadSuccess(true);
    toast.success('File uploaded');
    onUploadComplete?.(uploaded as AppFile);
    // Reset success state after 10 seconds to show dropzone again (longer for tests to detect)
    clearTimeout(successTimerRef.current);
    successTimerRef.current = setTimeout(() => {
      setUploadSuccess(false);
      setUploadProgress(null);
    }, 10000);
  };

  const handleFileSelect = async (file: globalThis.File) => {
    setUploadProgress(0);
    setUploadSuccess(false);
    setResumeMismatchError(null);
    const startTime = Date.now();

    // Resume routing: a checkpoint-targeted pick resumes the interrupted
    // upload. The fingerprint/size pre-check rejects a different file
    // BEFORE any mutation — resuming checkpoint X with file Y would
    // corrupt the multipart upload (multipartUploader.resume() carries
    // the same checks as defence-in-depth).
    if (pendingResumeFingerprint) {
      const checkpoint = checkpoints.find(
        (entry) => entry.fingerprint === pendingResumeFingerprint,
      );
      setPendingResumeFingerprint(null);
      if (checkpoint) {
        const pickedFingerprint = resumeUpload.computeFingerprint(file);
        if (
          !pickedFingerprint ||
          pickedFingerprint !== checkpoint.fingerprint ||
          file.size !== checkpoint.totalSize
        ) {
          setResumeMismatchError(
            'The selected file does not match the interrupted upload — pick the same file to resume, or discard the checkpoint.',
          );
          // The pick was rejected before any upload started — clear the
          // 0% progress marker so the dropzone doesn't sit in the
          // "Uploading..." state behind the mismatch error.
          setUploadProgress(null);
          return;
        }
        console.log(`[FileUpload] Resuming upload: ${file.name} (${file.size} bytes)`);
        try {
          const resumed = await resumeUpload.resume(file, checkpoint, {
            onProgress: (progress) => {
              setUploadProgress(progress);
            },
          });
          const duration = Date.now() - startTime;
          console.log(`[FileUpload] Resume completed in ${duration}ms: ${resumed.id}`);
          // The checkpoint is consumed by a completed resume.
          clearUploadCheckpoint(checkpoint.fingerprint);
          setCheckpoints((current) =>
            current.filter((entry) => entry.fingerprint !== checkpoint.fingerprint),
          );
          finishSuccess(resumed);
          return;
        } catch (error) {
          const duration = Date.now() - startTime;
          const err = error instanceof Error ? error : new Error('Resume failed');
          console.error(`[FileUpload] Resume failed after ${duration}ms:`, err);
          toast.error(getErrorMessage(error));
          onUploadError?.(err);
          setUploadProgress(null);
          setUploadSuccess(false);
          return;
        }
      }
      // Checkpoint disappeared between click and pick — fall through to
      // a fresh upload below.
    }

    console.log(`[FileUpload] Starting upload: ${file.name} (${file.size} bytes)`);

    try {
      // Fresh uploads go through the MultipartUploader engine (NOT the
      // legacy fileService.uploadFile single-PUT): the engine keeps the
      // single-PUT fast path for small files AND writes the GAP-A
      // baseline checkpoint the moment the backend requires multipart —
      // without the engine, a failed chunk PUT leaves no checkpoint and
      // the resume prompt can never surface (b7 #22).
      const uploadedFile = await resumeUpload.upload(file, {
        onProgress: (progress) => {
          setUploadProgress(progress);
          if (progress > 0 && progress < 100) {
            console.log(`[FileUpload] Progress: ${Math.round(progress)}%`);
          }
        },
      });
      const duration = Date.now() - startTime;
      console.log(`[FileUpload] Upload completed in ${duration}ms: ${uploadedFile.id}`);
      finishSuccess(uploadedFile);
    } catch (error) {
      const duration = Date.now() - startTime;
      const err = error instanceof Error ? error : new Error('Upload failed');
      console.error(`[FileUpload] Upload failed after ${duration}ms:`, err);
      toast.error(getErrorMessage(error));
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
    // A drop is a fresh-upload gesture — a canceled resume picker must
    // not mis-route the dropped file (same rule as handleClick).
    setPendingResumeFingerprint(null);
    setResumeMismatchError(null);
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
    // Dropzone click is a fresh-upload gesture — a canceled resume
    // picker must not mis-route the next selection.
    setPendingResumeFingerprint(null);
    setResumeMismatchError(null);
    fileInputRef.current?.click();
  };

  const isUploading =
    resumeUpload.isPending || (uploadProgress !== null && uploadProgress < 100);
  const showSuccess = uploadSuccess && uploadProgress === 100;

  return (
    // Phase 226.F1.b — data-testid on the wrapper + dropzone for stable
    // e2e selectors. The dropzone testid carries the upload state in a
    // suffix-free attribute so specs don't have to parse the className
    // template (`getByTestId('file-upload-dropzone')` works regardless
    // of dragging/uploading/success state).
    <div className="file-upload" data-testid="file-upload">
      {checkpoints.length > 0 && (
        <div className="file-upload-resume-prompt" data-testid="file-upload-resume-prompt">
          <p>Resume previous upload?</p>
          {checkpoints.map((checkpoint) => {
            const pct = Math.round(
              (checkpoint.completedParts.length / checkpoint.chunkCount) * 100,
            );
            return (
              <div
                key={checkpoint.fingerprint}
                className="file-upload-resume-entry"
                data-testid={`resume-entry-${checkpoint.fingerprint}`}
              >
                <span>{checkpoint.fileName}</span>
                <span>
                  {checkpoint.completedParts.length}/{checkpoint.chunkCount} parts uploaded (
                  {pct}%)
                </span>
                <button
                  type="button"
                  data-testid={`resume-btn-${checkpoint.fingerprint}`}
                  onClick={() => handleResumeClick(checkpoint.fingerprint)}
                >
                  Resume
                </button>
                <button
                  type="button"
                  data-testid={`discard-btn-${checkpoint.fingerprint}`}
                  onClick={() => handleDiscardCheckpoint(checkpoint.fingerprint)}
                >
                  Discard
                </button>
              </div>
            );
          })}
        </div>
      )}
      {resumeMismatchError && (
        // Phase 260.3.F.3 — inline mismatch terminal for the resume CTA
        // path (a picked file whose fingerprint/size doesn't match the
        // interrupted upload). Distinct from the generic ErrorDisplay so
        // the user gets the actionable fix ("pick the same file, or
        // discard") instead of a raw upload failure.
        <div className="file-upload-resume-error" role="alert" data-testid="resume-error">
          {resumeMismatchError}
        </div>
      )}
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
          // The input lives inside the dropzone; a click on it (including
          // the programmatic picker-open from handleResumeClick) must NOT
          // bubble to the dropzone's onClick — that handler clears
          // pendingResumeFingerprint and would silently re-route a resume
          // pick to a fresh upload.
          onClick={(e) => e.stopPropagation()}
          className="file-upload-input"
          data-testid="file-upload-input"
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
      {Boolean(resumeUpload.error) && (
        <ErrorDisplay
          error={resumeUpload.error}
          title="Upload failed"
          onRetry={() => resumeUpload.reset()}
        />
      )}
    </div>
  );
}
