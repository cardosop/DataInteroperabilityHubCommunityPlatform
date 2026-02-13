/**
 * Compliance Run List Page
 * Displays list of compliance runs with filtering; Create compliance run from list (OpenAPI ComplianceRunCreateRequest)
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useComplianceRuns, useCreateComplianceRun } from '../hooks/useCompliance';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import type { ComplianceRunStatus } from '../../../shared/types/compliance';
import './ComplianceRunListPage.css';

export function ComplianceRunListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [statusFilter, setStatusFilter] = useState<ComplianceRunStatus | ''>('');
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    asset_id: '',
    dataset_id: '',
    file_id: '',
    scan_mode: 'internal' as 'internal' | 'external',
    applicable_regulations: '',
  });
  const [createError, setCreateError] = useState<string | null>(null);

  const filters = {
    page,
    page_size: pageSize,
    ordering: '-created_at',
    status: statusFilter || undefined,
  };

  const { data, isLoading, error, refetch } = useComplianceRuns(filters);
  const createMutation = useCreateComplianceRun();

  const handleComplianceRunClick = (complianceRunId: string) => {
    navigate(`/compliance/runs/${complianceRunId}`);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    const payload = {
      asset_id: createForm.asset_id.trim() || undefined,
      dataset_id: createForm.dataset_id.trim() || undefined,
      file_id: createForm.file_id.trim() || undefined,
      scan_mode: createForm.scan_mode,
      applicable_regulations: createForm.applicable_regulations
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean).length
        ? createForm.applicable_regulations.split(',').map((s) => s.trim()).filter(Boolean)
        : undefined,
    };
    if (!payload.asset_id && !payload.dataset_id && !payload.file_id) {
      setCreateError('Provide at least one of: Asset ID, Dataset ID, or File ID');
      return;
    }
    try {
      const run = await createMutation.mutateAsync(payload);
      setCreateModalOpen(false);
      setCreateForm({
        asset_id: '',
        dataset_id: '',
        file_id: '',
        scan_mode: 'internal',
        applicable_regulations: '',
      });
      navigate(`/compliance/runs/${run.id}`);
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create compliance run');
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading compliance runs..." />;
  }

  if (error) {
    return (
      <ErrorDisplay error={error} title="Failed to load compliance runs" onRetry={() => refetch()} />
    );
  }

  if (!data || data.results.length === 0) {
    return (
      <div className="compliance-run-list-page">
        <div className="compliance-run-list-header">
          <h1>Compliance Runs</h1>
          <button
            type="button"
            className="btn-primary compliance-create-run-btn"
            onClick={() => setCreateModalOpen(true)}
          >
            Create compliance run
          </button>
        </div>
        <EmptyState
          title="No compliance runs found"
          message="Compliance runs will appear here when created. Use the button above to create a run."
        />
        {createModalOpen && (
          <div className="compliance-create-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="compliance-create-modal-title">
            <div className="compliance-create-modal">
              <h2 id="compliance-create-modal-title">Create compliance run</h2>
              <form onSubmit={handleCreateSubmit} className="compliance-create-form">
                <div className="form-group">
                  <label htmlFor="compliance-create-asset_id">Asset ID (optional)</label>
                  <input
                    id="compliance-create-asset_id"
                    type="text"
                    value={createForm.asset_id}
                    onChange={(e) => setCreateForm({ ...createForm, asset_id: e.target.value })}
                    placeholder="UUID"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="compliance-create-dataset_id">Dataset ID (optional)</label>
                  <input
                    id="compliance-create-dataset_id"
                    type="text"
                    value={createForm.dataset_id}
                    onChange={(e) => setCreateForm({ ...createForm, dataset_id: e.target.value })}
                    placeholder="UUID"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="compliance-create-file_id">File ID (optional)</label>
                  <input
                    id="compliance-create-file_id"
                    type="text"
                    value={createForm.file_id}
                    onChange={(e) => setCreateForm({ ...createForm, file_id: e.target.value })}
                    placeholder="UUID"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="compliance-create-scan_mode">Scan mode</label>
                  <select
                    id="compliance-create-scan_mode"
                    value={createForm.scan_mode}
                    onChange={(e) => setCreateForm({ ...createForm, scan_mode: e.target.value as 'internal' | 'external' })}
                  >
                    <option value="internal">Internal</option>
                    <option value="external">External</option>
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="compliance-create-regulations">Applicable regulations (comma-separated, optional)</label>
                  <input
                    id="compliance-create-regulations"
                    type="text"
                    value={createForm.applicable_regulations}
                    onChange={(e) => setCreateForm({ ...createForm, applicable_regulations: e.target.value })}
                    placeholder="e.g. GDPR, HIPAA"
                  />
                </div>
                {createError && <p className="compliance-create-error" role="alert">{createError}</p>}
                <div className="compliance-create-modal-actions">
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
        )}
      </div>
    );
  }

  return (
    <div className="compliance-run-list-page">
      <div className="compliance-run-list-header">
        <h1>Compliance Runs</h1>
        <div className="compliance-run-list-header-actions">
          <button
            type="button"
            className="btn-primary compliance-create-run-btn"
            onClick={() => setCreateModalOpen(true)}
          >
            Create compliance run
          </button>
          <div className="compliance-run-list-filters">
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as ComplianceRunStatus | '');
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

      {createModalOpen && (
        <div className="compliance-create-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="compliance-create-modal-title">
          <div className="compliance-create-modal">
            <h2 id="compliance-create-modal-title">Create compliance run</h2>
            <form onSubmit={handleCreateSubmit} className="compliance-create-form">
              <div className="form-group">
                <label htmlFor="compliance-create-asset_id">Asset ID (optional)</label>
                <input
                  id="compliance-create-asset_id"
                  type="text"
                  value={createForm.asset_id}
                  onChange={(e) => setCreateForm({ ...createForm, asset_id: e.target.value })}
                  placeholder="UUID"
                />
              </div>
              <div className="form-group">
                <label htmlFor="compliance-create-dataset_id">Dataset ID (optional)</label>
                <input
                  id="compliance-create-dataset_id"
                  type="text"
                  value={createForm.dataset_id}
                  onChange={(e) => setCreateForm({ ...createForm, dataset_id: e.target.value })}
                  placeholder="UUID"
                />
              </div>
              <div className="form-group">
                <label htmlFor="compliance-create-file_id">File ID (optional)</label>
                <input
                  id="compliance-create-file_id"
                  type="text"
                  value={createForm.file_id}
                  onChange={(e) => setCreateForm({ ...createForm, file_id: e.target.value })}
                  placeholder="UUID"
                />
              </div>
              <div className="form-group">
                <label htmlFor="compliance-create-scan_mode">Scan mode</label>
                <select
                  id="compliance-create-scan_mode"
                  value={createForm.scan_mode}
                  onChange={(e) => setCreateForm({ ...createForm, scan_mode: e.target.value as 'internal' | 'external' })}
                >
                  <option value="internal">Internal</option>
                  <option value="external">External</option>
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="compliance-create-regulations">Applicable regulations (comma-separated, optional)</label>
                <input
                  id="compliance-create-regulations"
                  type="text"
                  value={createForm.applicable_regulations}
                  onChange={(e) => setCreateForm({ ...createForm, applicable_regulations: e.target.value })}
                  placeholder="e.g. GDPR, HIPAA"
                />
              </div>
              {createError && <p className="compliance-create-error" role="alert">{createError}</p>}
              <div className="compliance-create-modal-actions">
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
      )}

      <div className="compliance-run-list-table">
        <table>
          <thead>
            <tr>
              <th>Regulations</th>
              <th>Status</th>
              <th>Overall Status</th>
              <th>Risk Level</th>
              <th>Allowed to Store</th>
              <th>Asset/Dataset</th>
              <th>Created</th>
              <th>Completed</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((run) => (
              <tr
                key={run.id}
                onClick={() => handleComplianceRunClick(run.id)}
                className="compliance-run-row"
              >
                <td>
                  {run.regulations && run.regulations.length > 0
                    ? run.regulations.join(', ')
                    : '-'}
                </td>
                <td>
                  <span className={`status-badge status-${run.status.toLowerCase()}`}>
                    {run.status}
                  </span>
                </td>
                <td>
                  {run.overall_status ? (
                    <span
                      className={`overall-status-badge overall-status-${run.overall_status.toLowerCase()}`}
                    >
                      {run.overall_status}
                    </span>
                  ) : (
                    '-'
                  )}
                </td>
                <td>
                  {run.risk_level ? (
                    <span className={`risk-level-badge risk-level-${run.risk_level.toLowerCase()}`}>
                      {run.risk_level}
                    </span>
                  ) : (
                    '-'
                  )}
                </td>
                <td>
                  {run.allowed_to_store !== undefined ? (
                    <span
                      className={`allowed-badge ${run.allowed_to_store ? 'allowed' : 'blocked'}`}
                    >
                      {run.allowed_to_store ? 'Yes' : 'No'}
                    </span>
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
        <div className="compliance-run-list-pagination">
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
