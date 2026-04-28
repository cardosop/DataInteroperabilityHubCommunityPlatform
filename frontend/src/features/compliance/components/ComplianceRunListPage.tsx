/**
 * Compliance Run List Page
 * Displays list of compliance runs with filtering; Create compliance run from list (OpenAPI ComplianceRunCreateRequest)
 */

import { useCallback, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useComplianceRuns } from '../hooks/useCompliance';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import type { ComplianceRunStatus } from '../../../shared/types/compliance';
import { ComplianceCreateModal } from './ComplianceCreateModal';
import './ComplianceRunListPage.css';
import { Button } from '../../../shared/components/Button';

export function ComplianceRunListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [statusFilter, setStatusFilter] = useState<ComplianceRunStatus | ''>('');
  const [createModalOpen, setCreateModalOpen] = useState(false);

  const filters = {
    page,
    page_size: pageSize,
    ordering: '-created_at',
    status: statusFilter || undefined,
  };

  const { data, isLoading, error, refetch } = useComplianceRuns(filters);

  const handleComplianceRunClick = (complianceRunId: string) => {
    navigate(`/compliance/runs/${complianceRunId}`);
  };

  // Track B PR 6: stable callbacks for the extracted modal.
  const closeModal = useCallback(() => setCreateModalOpen(false), []);
  const handleCreated = useCallback(
    (complianceRunId: string) => {
      setCreateModalOpen(false);
      navigate(`/compliance/runs/${complianceRunId}`);
    },
    [navigate],
  );

  // Track B structural inversion.
  let mainContent: ReactNode;
  if (isLoading) {
    mainContent = <ListPageSkeleton />;
  } else if (error) {
    mainContent = (
      <ErrorDisplay
        error={error}
        title="Failed to load compliance runs"
        onRetry={() => refetch()}
      />
    );
  } else if (!data || data.results.length === 0) {
    mainContent = (
      <EmptyState
        title="No compliance runs found"
        message="Compliance runs will appear here when created. Use the button above to create a run."
      />
    );
  } else {
    mainContent = (
      <>
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
                      <span
                        className={`risk-level-badge risk-level-${run.risk_level.toLowerCase()}`}
                      >
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
      </>
    );
  }

  return (
    // Phase 226.F1.b — testid for stable e2e selector.
    <div className="compliance-run-list-page" data-testid="compliance-run-list-page">
      <div className="compliance-run-list-header">
        <h1>Compliance Runs</h1>
        <div className="compliance-run-list-header-actions">
          <Button
            variant="primary"
            className="compliance-create-run-btn"
            data-testid="btn-create-compliance-run"
            onClick={() => setCreateModalOpen(true)}
          >
            Create compliance run
          </Button>
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
        <ComplianceCreateModal onClose={closeModal} onCreated={handleCreated} />
      )}

      {mainContent}
    </div>
  );
}
