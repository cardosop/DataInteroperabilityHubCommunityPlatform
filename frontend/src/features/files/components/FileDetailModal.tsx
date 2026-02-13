/**
 * File Detail Modal
 * Shows file metadata; used from FileListPage (view details).
 */

import type { File as FileType } from '../../../shared/types/files';
import './FileDetailModal.css';

interface FileDetailModalProps {
  file: FileType;
  onClose: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileDetailModal({ file, onClose }: FileDetailModalProps) {
  return (
    <div
      className="file-detail-modal-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="file-detail-title"
    >
      <div className="file-detail-modal" onClick={(e) => e.stopPropagation()}>
        <div className="file-detail-modal-header">
          <h2 id="file-detail-title">File Details</h2>
          <button
            type="button"
            className="file-detail-modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="file-detail-modal-body">
          <dl className="file-detail-dl">
            <dt>Name</dt>
            <dd>{file.name}</dd>
            <dt>Size</dt>
            <dd>{formatBytes(file.size)}</dd>
            <dt>Content type</dt>
            <dd>{file.content_type}</dd>
            <dt>Status</dt>
            <dd>
              <span
                className={`file-status-badge file-status-${(file.status ?? '').toLowerCase()}`}
              >
                {file.status}
              </span>
            </dd>
            <dt>Created</dt>
            <dd>{new Date(file.created_at).toLocaleString()}</dd>
            <dt>Updated</dt>
            <dd>{new Date(file.updated_at).toLocaleString()}</dd>
            <dt>ID</dt>
            <dd className="file-detail-id">{file.id}</dd>
            {'asset_id' in file && file.asset_id && (
              <>
                <dt>Asset</dt>
                <dd>
                  <a href={`/assets/${file.asset_id}`} className="file-detail-link">
                    {file.asset_id}
                  </a>
                </dd>
              </>
            )}
            {'dataset_id' in file && file.dataset_id && (
              <>
                <dt>Dataset</dt>
                <dd>
                  <a href={`/datasets/${file.dataset_id}`} className="file-detail-link">
                    {file.dataset_id}
                  </a>
                </dd>
              </>
            )}
          </dl>
        </div>
      </div>
    </div>
  );
}
