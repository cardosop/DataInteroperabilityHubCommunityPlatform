/**
 * DQ Run List Page
 * Displays list of DQ runs with filtering
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDQRuns, useCreateDQRun } from '../hooks/useDQ';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { AssetPicker } from '../../../shared/components/pickers/AssetPicker';
import { DatasetPicker } from '../../../shared/components/pickers/DatasetPicker';
import { FilePicker } from '../../../shared/components/pickers/FilePicker';
import type { DQRunStatus } from '../../../shared/types/dq';
import './DQRunListPage.css';

const VALID_PROFILE_KEYS = ['intake_basic_gx', 'intake_basic_soda'];

export function DQRunListPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [statusFilter, setStatusFilter] = useState<DQRunStatus | ''>('');
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    asset_id: '',
    dataset_id: '',
    file_id: '',
    profile_key: '',
  });
  const [createError, setCreateError] = useState<string | null>(null);

  const filters = {
    page,
    page_size: pageSize,
    ordering: '-created_at',
    status: statusFilter || undefined,
  };

  const { data, isLoading, error, refetch } = useDQRuns(filters);
  const createMutation = useCreateDQRun();

  const handleDQRunClick = (dqRunId: string) => {
    navigate(`/dq/runs/${dqRunId}`);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    const assetId = createForm.asset_id.trim() || undefined;
    const datasetId = createForm.dataset_id.trim() || undefined;
    const fileId = createForm.file_id.trim() || undefined;
    if (!assetId && !datasetId && !fileId) {
      setCreateError('Provide at least one of: Asset, Dataset, or File');
      return;
    }
    const payload = {
      asset_id: assetId,
      dataset_id: datasetId,
      file_id: fileId,
      profile_key: createForm.profile_key.trim() || undefined,
    };
    try {
      const run = await createMutation.mutateAsync(payload);
      setCreateModalOpen(false);
      setCreateForm({ asset_id: '', dataset_id: '', file_id: '', profile_key: '' });
      toast.success('DQ run created successfully.');
      navigate(`/dq/runs/${run.id}`);
    } catch (err: unknown) {
      const msg = normalizeError(err).error.message || 'Failed to create DQ run';
      setCreateError(msg);
      toast.error(msg);
    }
  };

  const renderCreateModal = () => (
    <div className="dq-create-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="dq-create-modal-title">
      <div className="dq-create-modal">
        <h2 id="dq-create-modal-title">Create DQ run</h2>
        <form onSubmit={handleCreateSubmit} className="dq-create-form">
          <div className="form-group">
            <label htmlFor="dq-create-asset_id">Asset (optional)</label>
            <AssetPicker
              value={createForm.asset_id || null}
              onChange={(id) => setCreateForm({ ...createForm, asset_id: id ?? '' })}
              placeholder="Search and select an asset..."
              data-testid="dq-create-asset-picker"
            />
          </div>
          <div className="form-group">
            <label htmlFor="dq-create-dataset_id">Dataset (optional)</label>
            <DatasetPicker
              value={createForm.dataset_id || null}
              onChange={(id) => setCreateForm({ ...createForm, dataset_id: id ?? '' })}
              assetId={createForm.asset_id || undefined}
              placeholder="Search and select a dataset..."
              data-testid="dq-create-dataset-picker"
            />
          </div>
          <div className="form-group">
            <label htmlFor="dq-create-file_id">File (optional)</label>
            <FilePicker
              value={createForm.file_id || null}
              onChange={(id) => setCreateForm({ ...createForm, file_id: id ?? '' })}
              assetId={createForm.asset_id || undefined}
              datasetId={createForm.dataset_id || undefined}
              placeholder="Search and select a file..."
              data-testid="dq-create-file-picker"
            />
          </div>
          <div className="form-group">
            <label htmlFor="dq-create-profile_key">Profile key (optional)</label>
            <select
              id="dq-create-profile_key"
              value={createForm.profile_key}
              onChange={(e) => setCreateForm({ ...createForm, profile_key: e.target.value })}
            >
              <option value="">Default</option>
              {VALID_PROFILE_KEYS.map((key) => (
                <option key={key} value={key}>
                  {key}
                </option>
              ))}
            </select>
          </div>
          {createError && <p className="dq-create-error" role="alert">{createError}</p>}
          <div className="dq-create-modal-actions">
            <button type="button" className="btn-secondary" onClick={() => setCreateModalOpen(false)}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  if (isLoading) {
    return <LoadingSpinner message="Loading DQ runs..." />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load DQ runs" onRetry={() => refetch()} />;
  }

  if (!data || data.results.length === 0) {
    return (
      <div className="dq-run-list-page">
        <div className="dq-run-list-header">
          <h1>Data Quality Runs</h1>
          <button
            type="button"
            className="btn-primary dq-create-run-btn"
            onClick={() => setCreateModalOpen(true)}
          >
            Create DQ run
          </button>
        </div>
        <EmptyState
          title="No DQ runs found"
          message="DQ runs will appear here when created. Use the button above to create a run."
        />
        {createModalOpen && renderCreateModal()}
      </div>
    );
  }

  return (
    <div className="dq-run-list-page">
      <div className="dq-run-list-header">
        <h1>Data Quality Runs</h1>
        <div className="dq-run-list-header-actions">
          <button
            type="button"
            className="btn-primary dq-create-run-btn"
            onClick={() => setCreateModalOpen(true)}
          >
            Create DQ run
          </button>
          <div className="dq-run-list-filters">
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as DQRunStatus | '');
              setPage(1);
            }}
          >
            <option value="">All Statuses</option>
            <option value="PENDING">Pending</option>
            <option value="RUNNING">Running</option>
            <option value="SUCCEEDED">Succeeded</option>
            <option value="FAILED">Failed</option>
          </select>
          </div>
        </div>
      </div>

      {createModalOpen && renderCreateModal()}

      <div className="dq-run-list-table">
        <table>
          <thead>
            <tr>
              <th>Profile</th>
              <th>Engine</th>
              <th>Status</th>
              <th>Overall Status</th>
              <th>Quality Score</th>
              <th>Asset/Dataset</th>
              <th>Created</th>
              <th>Completed</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((run) => (
              <tr
                key={run.id}
                onClick={() => handleDQRunClick(run.id)}
                className="dq-run-row"
              >
                <td>{run.profile_key}</td>
                <td>{run.engine}</td>
                <td>
                  <span className={`status-badge status-${run.status.toLowerCase()}`}>
                    {run.status}
                  </span>
                </td>
                <td>
                  {run.overall_status ? (
                    <span className={`overall-status-badge overall-status-${run.overall_status.toLowerCase()}`}>
                      {run.overall_status}
                    </span>
                  ) : (
                    '-'
                  )}
                </td>
                <td>
                  {run.quality_score !== null && run.quality_score !== undefined ? (
                    <span className="quality-score">{Math.round(run.quality_score * 100)}%</span>
                  ) : (
                    '-'
                  )}
                </td>
                <td>
                  {run.asset ? (
                    <span>Asset: {run.asset.slice(0, 8)}...</span>
                  ) : run.dataset ? (
                    <span>Dataset: {run.dataset.slice(0, 8)}...</span>
                  ) : run.file ? (
                    <span>File: {run.file.slice(0, 8)}...</span>
                  ) : (
                    '-'
                  )}
                </td>
                <td>{new Date(run.created_at).toLocaleString()}</td>
                <td>{run.completed_at ? new Date(run.completed_at).toLocaleString() : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.total_pages > 1 && (
        <div className="dq-run-list-pagination">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={!data.has_previous}
          >
            Previous
          </button>
          <span>
            Page {data.page} of {data.total_pages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
            disabled={!data.has_next}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
