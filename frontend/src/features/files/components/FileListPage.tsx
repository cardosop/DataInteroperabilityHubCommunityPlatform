/**
 * File List Page
 * Global file list with table, filters (asset_id, dataset_id if API supports), pagination,
 * view details (modal), delete with confirmation, upload. Uses fileService.list(), getById(), delete().
 */

import { useState, type ReactNode } from 'react';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { Modal } from '../../../shared/components/Modal';
import { useToast } from '../../../shared/components/Toast';
import { useDebouncedValue } from '../../../shared/hooks/useDebouncedValue';
import { normalizeError } from '../../../shared/utils/errorUtils';
import type { File as FileType } from '../../../shared/types/files';
import { useDeleteFile, useFiles } from '../hooks/useFiles';
import { FileDetailModal } from './FileDetailModal';
import { FileUpload } from './FileUpload';
import './FileListPage.css';
import { Button } from '../../../shared/components/Button';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileListPage() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [assetIdFilter, setAssetIdFilter] = useState('');
  const [datasetIdFilter, setDatasetIdFilter] = useState('');
  const [detailFile, setDetailFile] = useState<FileType | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<FileType | null>(null);
  const [showUploadModal, setShowUploadModal] = useState(false);

  const toast = useToast();
  // PR 5.3: debounce both text filters so typing doesn't spam the API.
  const debouncedAssetId = useDebouncedValue(assetIdFilter, 300);
  const debouncedDatasetId = useDebouncedValue(datasetIdFilter, 300);
  const filters = {
    page,
    page_size: pageSize,
    asset_id: debouncedAssetId.trim() || undefined,
    dataset_id: debouncedDatasetId.trim() || undefined,
  };

  const { data, isLoading, error, refetch } = useFiles(filters);
  const deleteMutation = useDeleteFile();

  const handleViewDetails = (file: FileType) => {
    setDetailFile(file);
  };

  const handleDeleteClick = (file: FileType, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteTarget(file);
  };

  const handleCancelDelete = () => setDeleteTarget(null);

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    const id = deleteTarget.id;
    setDeleteTarget(null);
    try {
      await deleteMutation.mutateAsync(id);
      toast.success('File deleted.');
      refetch();
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to delete file');
    }
  };

  const handleUploadComplete = (file: FileType) => {
    refetch();
    toast.success(`File "${file.name}" uploaded successfully.`);
    setShowUploadModal(false);
  };

  const handleUploadError = (err: unknown) => {
    toast.error(normalizeError(err).error.message || 'Upload failed');
  };

  const results = data?.results ?? [];
  const totalPages = data?.total_pages ?? 0;
  const hasFilters = !!(debouncedAssetId.trim() || debouncedDatasetId.trim());

  // Track B structural inversion: header + filter bar render unconditionally.
  let mainContent: ReactNode;
  if (isLoading) {
    mainContent = <ListPageSkeleton />;
  } else if (error) {
    mainContent = (
      <ErrorDisplay error={error} title="Failed to load files" onRetry={() => refetch()} />
    );
  } else if (!data || results.length === 0) {
    mainContent = (
      <EmptyState
        data-testid="file-list-empty-state"
        title="No files found"
        message={
          hasFilters
            ? 'Try adjusting filters or clear them to see all files.'
            : 'Upload a file using the button above, or from an asset or dataset.'
        }
        action={
          hasFilters
            ? {
                label: 'Clear filters',
                onClick: () => {
                  setAssetIdFilter('');
                  setDatasetIdFilter('');
                  setPage(1);
                },
              }
            : { label: 'Upload File', onClick: () => setShowUploadModal(true) }
        }
      />
    );
  } else {
    mainContent = (
      <>
        <div className="file-list-table-wrapper" data-testid="file-list-table-wrapper">
          <table className="file-list-table" data-testid="file-list-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Size</th>
                <th>Type</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {results.map((file) => (
                <tr key={file.id} className="file-list-row" data-file-name={file.name}>
                  <td>
                    <button
                      type="button"
                      className="file-list-name-btn"
                      onClick={() => handleViewDetails(file)}
                    >
                      {file.name}
                    </button>
                  </td>
                  <td>{formatBytes(file.size)}</td>
                  <td>{file.content_type}</td>
                  <td>
                    <span
                      className={`file-list-status file-list-status-${(file.status ?? '').toLowerCase()}`}
                    >
                      {file.status}
                    </span>
                  </td>
                  <td>{new Date(file.created_at).toLocaleString()}</td>
                  <td>
                    <button
                      type="button"
                      className="file-list-action-btn file-list-action-view"
                      onClick={() => handleViewDetails(file)}
                    >
                      View
                    </button>
                    <button
                      type="button"
                      className="file-list-action-btn file-list-action-delete"
                      onClick={(e) => handleDeleteClick(file, e)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="file-list-pagination">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={!data.has_previous}
            >
              Previous
            </button>
            <span>
              Page {data.page} of {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={!data.has_next}
            >
              Next
            </button>
          </div>
        )}

        {deleteMutation.isError && (
          <ErrorDisplay
            error={deleteMutation.error}
            title="Failed to delete file"
            onRetry={() => deleteMutation.reset()}
          />
        )}
      </>
    );
  }

  return (
    <div className="file-list-page" data-testid="file-list-page">
      <div className="file-list-header" data-testid="file-list-header">
        <h1>Files</h1>
        <Button
          variant="primary"
          className="file-list-upload-btn"
          onClick={() => setShowUploadModal(true)}
          data-testid="btn-upload-file"
        >
          Upload File
        </Button>
      </div>

      <div className="file-list-filters" data-testid="file-list-filters">
        <input
          type="text"
          placeholder="Asset ID (optional)"
          value={assetIdFilter}
          onChange={(e) => {
            setAssetIdFilter(e.target.value);
            setPage(1);
          }}
          className="file-list-filter-input"
        />
        <input
          type="text"
          placeholder="Dataset ID (optional)"
          value={datasetIdFilter}
          onChange={(e) => {
            setDatasetIdFilter(e.target.value);
            setPage(1);
          }}
          className="file-list-filter-input"
        />
      </div>

      {mainContent}

      {detailFile && <FileDetailModal file={detailFile} onClose={() => setDetailFile(null)} />}

      {showUploadModal && (
        <Modal
          isOpen={showUploadModal}
          onClose={() => setShowUploadModal(false)}
          title="Upload File"
          aria-describedby="file-upload-description"
        >
          <div id="file-upload-description">
            <FileUpload
              onUploadComplete={handleUploadComplete}
              onUploadError={handleUploadError}
              accept=".csv,.json,.parquet"
            />
          </div>
        </Modal>
      )}

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        onClose={handleCancelDelete}
        onConfirm={handleDeleteConfirm}
        title="Delete file"
        message={
          deleteTarget
            ? `Are you sure you want to delete "${deleteTarget.name}"? This cannot be undone.`
            : ''
        }
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  );
}
