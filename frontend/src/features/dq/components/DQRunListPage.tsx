/**
 * DQ Run List Page
 * Displays list of DQ runs with filtering
 */

import { useCallback, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDQRuns } from '../hooks/useDQ';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import type { DQRunStatus } from '../../../shared/types/dq';
import { DQCreateModal } from './DQCreateModal';
import './DQRunListPage.css';
import { Button } from '../../../shared/components/Button';

export function DQRunListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [statusFilter, setStatusFilter] = useState<DQRunStatus | ''>('');
  const [createModalOpen, setCreateModalOpen] = useState(false);

  const filters = {
    page,
    page_size: pageSize,
    ordering: '-created_at',
    status: statusFilter || undefined,
  };

  const { data, isLoading, error, refetch } = useDQRuns(filters);

  const handleDQRunClick = (dqRunId: string) => {
    navigate(`/dq/runs/${dqRunId}`);
  };

  // Track B PR 6: stable callbacks for the extracted modal so its props
  // identity doesn't bust on every parent render.
  const closeModal = useCallback(() => setCreateModalOpen(false), []);
  const handleCreated = useCallback(
    (dqRunId: string) => {
      setCreateModalOpen(false);
      navigate(`/dq/runs/${dqRunId}`);
    },
    [navigate],
  );

  // Track B structural inversion: header + filter (status) render unconditionally.
  let mainContent: ReactNode;
  if (isLoading) {
    mainContent = <ListPageSkeleton />;
  } else if (error) {
    mainContent = (
      <ErrorDisplay error={error} title="Failed to load DQ runs" onRetry={() => refetch()} />
    );
  } else if (!data || data.results.length === 0) {
    mainContent = (
      <EmptyState
        title="No DQ runs found"
        message="DQ runs will appear here when created. Use the button above to create a run."
      />
    );
  } else {
    mainContent = (
      <>
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
                    {run.quality_score !== null && run.quality_score !== undefined ? (
                      <span className="quality-score">{Math.round(run.quality_score)}%</span>
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
      </>
    );
  }

  return (
    <div className="dq-run-list-page">
      <div className="dq-run-list-header">
        <h1>Data Quality Runs</h1>
        <div className="dq-run-list-header-actions">
          <Button
            variant="primary"
            className="dq-create-run-btn"
            data-testid="btn-create-dq-run"
            onClick={() => setCreateModalOpen(true)}
          >
            Create DQ run
          </Button>
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

      {createModalOpen && (
        <DQCreateModal onClose={closeModal} onCreated={handleCreated} />
      )}

      {mainContent}
    </div>
  );
}
