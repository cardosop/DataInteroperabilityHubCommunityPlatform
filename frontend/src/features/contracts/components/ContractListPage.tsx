/**
 * Contract List Page
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { useContracts } from '../hooks/useContracts';
import './ContractListPage.css';
import { Button } from '../../../shared/components/Button';

export function ContractListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const { data, isLoading, error, refetch } = useContracts({
    page,
    page_size: 50,
    ordering: '-created_at',
  });

  if (isLoading) return <ListPageSkeleton />;
  if (error)
    return (
      <ErrorDisplay error={error} title="Failed to load contracts" onRetry={() => refetch()} />
    );
  const handleCreateContract = () => navigate('/odps/upload');

  if (!data || data.results.length === 0) {
    return (
      <EmptyState
        data-testid="contract-list-empty-state"
        title="No contracts found"
        message="Get started by creating your first contract."
        action={{ label: 'Create Contract', onClick: handleCreateContract }}
      />
    );
  }

  return (
    <div className="contract-list-page" data-testid="contract-list-page">
      <div className="contract-list-header" data-testid="contract-list-header">
        <h1>Contracts</h1>
        <Button variant="primary" onClick={handleCreateContract}>
          Create Contract
        </Button>
      </div>
      <div className="contract-list-table" data-testid="contract-list-table">
        <table role="table" aria-label="Contracts list">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Format</th>
              <th scope="col">Status</th>
              <th scope="col">Validation</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((contract) => (
              <tr
                key={contract.id}
                onClick={() => navigate(`/contracts/${contract.id}`)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    navigate(`/contracts/${contract.id}`);
                  }
                }}
                className="contract-row"
                role="row"
                tabIndex={0}
                aria-label={`Contract ${contract.name || 'Unnamed'}`}
              >
                <td>
                  <strong>{contract.name || 'Unnamed Contract'}</strong>
                </td>
                <td>{contract.original_format ?? '—'}</td>
                <td>
                  <span
                    className={`status-badge status-${(contract.normalization_status ?? '').toLowerCase().replace('_', '-')}`}
                    aria-label={`Status: ${contract.normalization_status ?? '—'}`}
                  >
                    {contract.normalization_status ?? '—'}
                  </span>
                </td>
                <td>
                  <span
                    className={`validation-badge validation-${(contract.validation_status ?? '').toLowerCase()}`}
                    aria-label={`Validation: ${contract.validation_status ?? '—'}`}
                  >
                    {contract.validation_status ?? '—'}
                  </span>
                </td>
                <td>{new Date(contract.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.total_pages > 1 && (
        <div className="contract-list-pagination">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={!data.has_previous}>
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
