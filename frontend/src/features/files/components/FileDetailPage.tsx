/**
 * Deep-linkable file detail surface at ``/files/:id``.
 *
 * Composition:
 *   - ``ScanStatusBanner`` at the top — short-circuits to ``null``
 *     when the scan is CLEAN.
 *   - Metadata block (name/size/content_type/status/scan/timestamps/IDs).
 *   - Download CTA — routes through ``triggerVerifiedDownload`` for
 *     SHA-256-stamped files with a presigned-URL fallback for legacy
 *     files. Disabled by ``canDownloadFile``.
 *   - ``ActivityTimeline`` for the audit log (resource_type=FILE).
 *   - Delete CTA with ``ConfirmDialog``; on success, navigates back to
 *     the list and invalidates the React Query cache.
 *
 * Live scan-status: ``useFileScanStatus`` polls every 2 s while the
 * status is ``PENDING_SCAN``. When the polled value is available it
 * overrides the value from the initial ``GET /files/{id}`` response
 * so the banner + pill update without a full page refetch.
 */

import { useNavigate, useParams, Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { Button } from '../../../shared/components/Button';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { ActivityTimeline } from '../../../shared/components/ActivityTimeline';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { FileScanStatus, type File as FileType } from '../../../shared/types/files';

import { fileService } from '../services/fileService';
import { useDeleteFile, useFile, useRenameFile } from '../hooks/useFiles';
import { useFileScanStatus } from '../hooks/useFileScanStatus';
import { canDownloadFile } from '../utils/fileDownloadPolicy';
import { openPresignedDownloadUrl } from '../utils/presignedDownloadNavigation';
import { triggerVerifiedDownload } from '../utils/triggerVerifiedDownload';
import {
  ChecksumMismatchError,
  FileTooLargeForVerificationError,
} from '../utils/downloadFileWithVerification';
import { ScanStatusBanner } from './ScanStatusBanner';
import { ScanStatusPill } from './ScanStatusPill';
import './FileDetailPage.css';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Scan-status values that signal "no further polling, persist this." */
const TERMINAL_SCAN_STATUSES: ReadonlySet<string> = new Set([
  'CLEAN',
  'INFECTED',
  'SCAN_ERROR',
  'SCAN_UNAVAILABLE',
]);

export function FileDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();

  const { data: file, isLoading, error, refetch } = useFile(id ?? null);
  const deleteMutation = useDeleteFile();
  const renameMutation = useRenameFile();

  const baselineScanStatus = file?.scan_status ?? null;
  const isPolling = baselineScanStatus === FileScanStatus.PENDING_SCAN;
  // Live scan-status — polls only while PENDING_SCAN. Once a terminal
  // outcome lands the hook stops on its own.
  const { scanStatus: polledScanStatus, scannedAt: polledScannedAt } = useFileScanStatus(
    id ?? null,
    { enabled: Boolean(id) && isPolling },
  );

  const effectiveScanStatus =
    (polledScanStatus as FileType['scan_status']) ?? file?.scan_status ?? FileScanStatus.PENDING_SCAN;
  const effectiveScannedAt = polledScannedAt ?? file?.scanned_at ?? null;

  // R1 audit GAP-F — propagate the polled terminal scan-status onto the
  // ``useFile`` cache so navigating away from the page and back doesn't
  // surface the stale ``PENDING_SCAN`` value baked into the initial
  // fetch. Without this patch the page polled silently and the
  // listing surface (FileListPage) + future detail-page mounts would
  // see ``PENDING_SCAN`` until React Query's 5-minute ``staleTime``
  // expired AND the user re-fetched.
  useEffect(() => {
    if (!id || !file) return;
    if (typeof polledScanStatus !== 'string') return;
    if (!TERMINAL_SCAN_STATUSES.has(polledScanStatus)) return;
    if (
      file.scan_status === polledScanStatus &&
      (file.scanned_at ?? null) === (polledScannedAt ?? null)
    ) {
      return;
    }
    queryClient.setQueryData<FileType | undefined>(
      ['files', 'detail', id],
      (cached) =>
        cached
          ? {
              ...cached,
              scan_status: polledScanStatus as FileScanStatus,
              scanned_at: polledScannedAt ?? cached.scanned_at,
            }
          : cached,
    );
    // List cache is best-effort: invalidate so the next mount of
    // ``FileListPage`` re-fetches with the fresh scan_status. Don't
    // refetch eagerly — it would cause a network blip on a page the
    // user might never visit again.
    queryClient.invalidateQueries({ queryKey: ['files', 'list'], refetchType: 'none' });
  }, [id, file, polledScanStatus, polledScannedAt, queryClient]);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameDraft, setRenameDraft] = useState('');

  if (isLoading) {
    return (
      <div data-testid="file-detail-page-loading">
        <DetailPageSkeleton />
      </div>
    );
  }

  if (error || !file) {
    return (
      <ErrorDisplay
        error={error || new Error('File not found')}
        title="Failed to load file"
        onRetry={() => refetch()}
      />
    );
  }

  // Composite view-model for downstream policy checks — the polled
  // scan_status overrides the value baked into the initial fetch.
  const viewFile: Pick<FileType, 'status' | 'scan_status'> = {
    status: file.status,
    scan_status: effectiveScanStatus,
  };

  const handleDownload = async () => {
    if (!canDownloadFile(viewFile)) return;
    try {
      // Phase 260.3.G — verified download for SHA-256-stamped files;
      // legacy files (`content_sha256 == null`) fall through to the
      // presigned-URL navigation path.
      if (file.content_sha256) {
        await triggerVerifiedDownload(file.id, {
          fileSizeBytes: typeof file.size === 'number' ? file.size : undefined,
        });
        return;
      }
      const payload = await fileService.getDownloadPayload(file.id);
      openPresignedDownloadUrl(payload.download_url);
    } catch (err) {
      if (err instanceof ChecksumMismatchError) {
        toast.error(
          `Download blocked — file integrity check failed (expected ` +
            `${err.expected.slice(0, 16)}…, got ${err.actual.slice(0, 16)}…). ` +
            `The corruption has been reported. Please try again or contact support.`,
        );
        return;
      }
      if (err instanceof FileTooLargeForVerificationError) {
        toast.info(
          `File is too large for in-browser SHA-256 verification ` +
            `(${err.size} bytes). Starting unverified download — use the ` +
            `SDK if you need a verified download.`,
        );
        openPresignedDownloadUrl(err.downloadUrl);
        return;
      }
      toast.error(normalizeError(err).error.message || 'Failed to start download');
    }
  };

  const handleDeleteConfirm = async () => {
    setShowDeleteConfirm(false);
    try {
      await deleteMutation.mutateAsync(file.id);
      toast.success('File deleted.');
      navigate('/files');
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to delete file');
    }
  };

  // Phase 260.4.C — display-name rename. Storage path is immutable;
  // only the human-facing ``File.name`` field is editable.
  const handleStartRename = () => {
    setRenameDraft(file.name);
    setIsRenaming(true);
  };

  const handleCancelRename = () => {
    setIsRenaming(false);
    setRenameDraft('');
  };

  const trimmedDraft = renameDraft.trim();
  const renameDraftIsValid = trimmedDraft.length > 0 && trimmedDraft.length <= 255;
  const renameDraftIsChanged = trimmedDraft !== file.name;

  const handleSaveRename = async () => {
    if (!renameDraftIsValid) return;
    if (!renameDraftIsChanged) {
      // No-op — close the editor without firing the mutation. This
      // mirrors the backend's idempotent same-name handling and saves
      // a network round-trip.
      handleCancelRename();
      return;
    }
    try {
      await renameMutation.mutateAsync({ id: file.id, name: trimmedDraft });
      setIsRenaming(false);
      setRenameDraft('');
    } catch (err) {
      // Mutation hook surfaces a toast via ``useMutationWithNotification``;
      // surface the structured error too for accessibility.
      toast.error(normalizeError(err).error.message || 'Failed to rename file');
    }
  };

  return (
    <div className="file-detail-page" data-testid="file-detail-page">
      <div className="file-detail-page-header">
        <Button onClick={() => navigate('/files')} variant="ghost">
          ← Back to Files
        </Button>
        <div className="file-detail-page-actions">
          {!isRenaming && (
            <Button
              onClick={handleStartRename}
              variant="secondary"
              data-testid="file-detail-rename-btn"
            >
              Rename
            </Button>
          )}
          <Button
            onClick={() => void handleDownload()}
            variant="primary"
            disabled={!canDownloadFile(viewFile)}
            data-testid="file-detail-download-btn"
            title={
              canDownloadFile(viewFile)
                ? 'Download file via secure link'
                : 'Download is unavailable until the file is ready and malware scanning allows it.'
            }
          >
            Download
          </Button>
          <Button
            onClick={() => setShowDeleteConfirm(true)}
            variant="danger"
            loading={deleteMutation.isPending}
            data-testid="file-detail-delete-btn"
          >
            Delete
          </Button>
        </div>
      </div>

      <div className="file-detail-page-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Files', href: '/files' },
            { label: file.name || 'File' },
          ]}
        />

        {/* Banner short-circuits to null on CLEAN. ``updated_at`` is
            the post-upload timestamp (close to scan-start); using
            ``created_at`` would over-count elapsed time by the upload
            duration on large files. */}
        <ScanStatusBanner
          scanStatus={effectiveScanStatus ?? FileScanStatus.PENDING_SCAN}
          size={file.size}
          scanStartedAt={file.updated_at ?? file.created_at}
        />

        <h1 className="file-detail-page-title">{file.name}</h1>

        <dl className="file-detail-dl">
          <dt>Name</dt>
          <dd>
            {isRenaming ? (
              <form
                className="file-detail-rename-form"
                data-testid="file-detail-rename-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  void handleSaveRename();
                }}
              >
                <label htmlFor="file-detail-rename-input" className="file-detail-rename-label">
                  New name
                </label>
                <input
                  id="file-detail-rename-input"
                  type="text"
                  value={renameDraft}
                  onChange={(e) => setRenameDraft(e.target.value)}
                  maxLength={255}
                  className="file-detail-rename-input"
                  data-testid="file-detail-rename-input"
                  autoFocus
                  aria-invalid={renameDraft.trim().length === 0 ? 'true' : 'false'}
                />
                <div className="file-detail-rename-actions">
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={!renameDraftIsValid}
                    loading={renameMutation.isPending}
                    data-testid="file-detail-rename-save-btn"
                  >
                    Save
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={handleCancelRename}
                    disabled={renameMutation.isPending}
                    data-testid="file-detail-rename-cancel-btn"
                  >
                    Cancel
                  </Button>
                </div>
                {/* Validation hint — surfaces only when the input is
                    invalid so the user knows why Save is disabled. */}
                {!renameDraftIsValid ? (
                  <p
                    className="file-detail-rename-error"
                    role="alert"
                    data-testid="file-detail-rename-error"
                  >
                    Name must not be empty and must be at most 255 characters.
                  </p>
                ) : null}
              </form>
            ) : (
              <span data-testid="file-detail-name-value">{file.name}</span>
            )}
          </dd>
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
          <dt>Scan status</dt>
          <dd>
            <ScanStatusPill
              testId="file-detail-scan-pill"
              status={effectiveScanStatus ?? FileScanStatus.PENDING_SCAN}
              scannedAt={effectiveScannedAt}
            />
          </dd>
          {effectiveScannedAt != null && effectiveScannedAt !== '' ? (
            <>
              <dt>Scanned at</dt>
              <dd>{new Date(effectiveScannedAt).toLocaleString()}</dd>
            </>
          ) : null}
          <dt>Created</dt>
          <dd>{new Date(file.created_at).toLocaleString()}</dd>
          <dt>Updated</dt>
          <dd>{new Date(file.updated_at).toLocaleString()}</dd>
          <dt>ID</dt>
          <dd className="file-detail-id">
            <UuidWithCopy value={file.id} label="File ID" />
          </dd>
          {file.asset_id ? (
            <>
              <dt>Asset</dt>
              <dd className="file-detail-id-ref">
                <UuidWithCopy value={file.asset_id} label="Asset ID" />
                <Link to={`/assets/${file.asset_id}`} className="file-detail-link">
                  View asset
                </Link>
              </dd>
            </>
          ) : null}
          {file.dataset_id ? (
            <>
              <dt>Dataset</dt>
              <dd className="file-detail-id-ref">
                <UuidWithCopy value={file.dataset_id} label="Dataset ID" />
                <Link to={`/datasets/${file.dataset_id}`} className="file-detail-link">
                  View dataset
                </Link>
              </dd>
            </>
          ) : null}
        </dl>

        <section
          className="file-detail-activity-section"
          data-testid="file-detail-activity-section"
          aria-labelledby="file-detail-activity-heading"
        >
          <h2 id="file-detail-activity-heading">Audit log</h2>
          <ActivityTimeline resourceType="FILE" resourceId={file.id} />
        </section>
      </div>

      {deleteMutation.isError && (
        <ErrorDisplay
          error={deleteMutation.error}
          title="Failed to delete file"
          onRetry={() => deleteMutation.reset()}
        />
      )}

      <ConfirmDialog
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={handleDeleteConfirm}
        title="Delete file"
        message={`Are you sure you want to delete "${file.name}"? This cannot be undone.`}
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  );
}
