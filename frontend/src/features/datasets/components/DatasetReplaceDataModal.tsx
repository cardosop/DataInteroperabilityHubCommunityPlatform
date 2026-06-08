/**
 * Phase 260.4.D — modal hosting the upload + refresh flow.
 *
 * Sequence:
 *   1. User clicks Replace Data on DatasetDetailPage → modal opens.
 *   2. User uploads a file via the existing FileUpload component
 *      (multipart-aware, scan-status-aware, SHA-256-stamped).
 *   3. On upload-complete, this modal IMMEDIATELY calls
 *      ``POST /datasets/{id}/refresh-from-file/`` with the new
 *      file_id.  The user does not click a separate "Continue" CTA —
 *      the upload IS the refresh trigger.
 *   4. On refresh-success the modal calls ``onSuccess(response)``
 *      with the new dataset + drift summary so the parent page can
 *      navigate to the new dataset and surface the drift banner.
 *   5. On refresh-error the modal stays open with an ErrorDisplay so
 *      the user can retry or cancel without losing their seat.
 *
 * The modal does NOT poll scan-status before triggering refresh —
 * that gate is enforced server-side (FILE_SCAN_NOT_CLEAN → 400).
 * Trying to gate client-side AND server-side risks divergence.
 */

import { useState, type JSX } from 'react';

import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { Modal } from '../../../shared/components/Modal';
import type { File as AppFile } from '../../../shared/types/files';
import { FileUpload } from '../../files/components/FileUpload';
import { useRefreshDatasetFromFile } from '../hooks/useDatasets';
import type { DatasetRefreshFromFileResponse } from '../services/datasetService';

export interface DatasetReplaceDataModalProps {
  open: boolean;
  datasetId: string;
  datasetName: string;
  onCancel: () => void;
  onSuccess: (response: DatasetRefreshFromFileResponse) => void;
}

export function DatasetReplaceDataModal({
  open,
  datasetId,
  datasetName,
  onCancel,
  onSuccess,
}: DatasetReplaceDataModalProps): JSX.Element | null {
  const refreshMutation = useRefreshDatasetFromFile();
  const [uploadError, setUploadError] = useState<Error | null>(null);

  if (!open) return null;

  const handleUploadComplete = async (_file: AppFile) => {
    setUploadError(null);
    try {
      const response = await refreshMutation.mutateAsync({
        datasetId,
      });
      onSuccess(response);
    } catch {
      // ``useMutationWithNotification`` surfaces the toast; the
      // ErrorDisplay below renders the structured error inline so
      // the user sees the failure without dismissing the toast.
    }
  };

  const handleUploadError = (err: Error) => {
    setUploadError(err);
  };

  return (
    <Modal
      isOpen={open}
      onClose={onCancel}
      title={`Replace data for "${datasetName}"`}
      aria-describedby="dataset-replace-description"
    >
      <div
        id="dataset-replace-description"
        data-testid="dataset-replace-modal-body"
      >
        <p className="dataset-replace-explainer">
          Upload a new file to create the next version of this dataset. The
          existing version is preserved as the parent — you'll be able to
          compare versions afterwards.
        </p>

        <FileUpload
          onUploadComplete={(file) => void handleUploadComplete(file)}
          onUploadError={handleUploadError}
          accept=".csv,.json,.parquet"
        />

        {refreshMutation.isPending && (
          <p
            className="dataset-replace-pending"
            role="status"
            data-testid="dataset-replace-refresh-pending"
          >
            Creating new dataset version…
          </p>
        )}

        {uploadError && (
          <ErrorDisplay
            error={uploadError}
            title="Upload failed"
            onRetry={() => setUploadError(null)}
          />
        )}

        {refreshMutation.isError && (
          <ErrorDisplay
            error={refreshMutation.error}
            title="Failed to refresh dataset"
            onRetry={() => refreshMutation.reset()}
          />
        )}

        <div className="dataset-replace-actions">
          <Button
            type="button"
            variant="secondary"
            onClick={onCancel}
            disabled={refreshMutation.isPending}
            data-testid="dataset-replace-cancel-btn"
          >
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  );
}
