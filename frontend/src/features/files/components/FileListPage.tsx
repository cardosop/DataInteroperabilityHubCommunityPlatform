/**
 * File List Page
 * Global file list with table, filters (asset_id, dataset_id if API supports), pagination,
 * view details (modal), delete with confirmation. Uses fileService.list(), getById(), delete().
 */

import { useState } from 'react';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { File as FileType } from '../../../shared/types/files';
import { useDeleteFile, useFiles } from '../hooks/useFiles';
import { FileDetailModal } from './FileDetailModal';
import './FileListPage.css';

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

  const filters = {
    page,
    page_size: pageSize,
    asset_id: assetIdFilter.trim() || undefined,
    dataset_id: datasetIdFilter.trim() || undefined,
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

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteMutation.mutateAsync(deleteTarget.id);
      setDeleteTarget(null);
      refetch();
    } catch {
      // Error handled by mutation
    }
  };

  const handleCancelDelete = () => {
    setDeleteTarget(null);
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading files..." />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load files" onRetry={() => refetch()} />;
  }

  const results = data?.results ?? [];
  const totalPages = data?.total_pages ?? 0;
  const hasFilters = assetIdFilter.trim() || datasetIdFilter.trim();

  if (!data || results.length === 0) {
    return (
      <div className="file-list-page">
        <div className="file-list-header">
          <h1>Files</h1>
        </div>
        <div className="file-list-filters">
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
        <EmptyState
          title="No files found"
          message={
            hasFilters
              ? 'Try adjusting filters.'
              : 'Upload a file from an asset or dataset to see it here.'
          }
        />
        {detailFile && <FileDetailModal file={detailFile} onClose={() => setDetailFile(null)} />}
      </div>
    );
  }

  return (
    <div className="file-list-page">
      <div className="file-list-header">
        <h1>Files</h1>
      </div>

      <div className="file-list-filters">
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

      <div className="file-list-table-wrapper">
        <table className="file-list-table">
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

      {detailFile && <FileDetailModal file={detailFile} onClose={() => setDetailFile(null)} />}

      {deleteTarget && (
        <div
          className="file-list-delete-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-dialog-title"
        >
          <div className="file-list-delete-dialog">
            <h3 id="delete-dialog-title">Delete file?</h3>
            <p>
              Are you sure you want to delete <strong>{deleteTarget.name}</strong>? This cannot be
              undone.
            </p>
            <div className="file-list-delete-actions">
              <button type="button" className="file-list-cancel-btn" onClick={handleCancelDelete}>
                Cancel
              </button>
              <button
                type="button"
                className="file-list-confirm-delete-btn"
                onClick={handleConfirmDelete}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
