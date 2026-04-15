/**
 * Contract List Page
 *
 * Displays all contracts with spec_type column and filter.
 * "Create Contract" navigates to /contracts/create (unified creation).
 */

import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { BulkActionBar } from '../../../shared/components/BulkActionBar';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { useBulkSelection } from '../../../shared/hooks/useBulkSelection';
import { exportToCSV } from '../../../shared/utils/exportUtils';
import { contractService } from '../services/contractService';
import { useContracts } from '../hooks/useContracts';
import { useToast } from '../../../shared/components/Toast';
import { Button } from '../../../shared/components/Button';
import './ContractListPage.css';

const SPEC_TYPE_OPTIONS = ['', 'ODPS', 'ODCS', 'HUB'] as const;
type SpecType = (typeof SPEC_TYPE_OPTIONS)[number];

function isValidSpecType(value: string): value is SpecType {
  return (SPEC_TYPE_OPTIONS as readonly string[]).includes(value);
}

export function ContractListPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [page, setPage] = useState(1);

  // Read spec_type from URL query parameter (e.g. /contracts?spec_type=ODPS
  // from the /odps backward-compatibility redirect). Fall back to '' (all).
  const urlSpecType = searchParams.get('spec_type') ?? '';
  const specTypeFilter = isValidSpecType(urlSpecType) ? urlSpecType : '';

  const { data, isLoading, error, refetch } = useContracts({
    page,
    page_size: 50,
    ordering: '-created_at',
    spec_type: specTypeFilter || undefined,
  });
  const toast = useToast();
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);

  const contractRows = data?.results ?? [];
  // DRAFT-only bulk delete: same guardrail as AssetListPage — deleting
  // ACTIVE/RETIRED contracts could orphan live assets. Rows without a
  // `status` field (older responses) are treated as non-selectable so
  // the safe default wins.
  const selection = useBulkSelection({
    allIds: contractRows.map((c) => c.id),
    isSelectable: (id) => contractRows.find((c) => c.id === id)?.status === 'DRAFT',
  });

  const handleBulkDelete = async () => {
    if (selection.selectedIds.length === 0) return;
    const count = selection.selectedIds.length;
    const ok = window.confirm(
      `Delete ${count} DRAFT contract${count === 1 ? '' : 's'}? This cannot be undone.`,
    );
    if (!ok) return;
    // Raw service, not `useDeleteContract` — the notification-wrapped
    // mutation fires one toast per call, which would spam N toasts for
    // a bulk delete. One summary toast below is the right UX.
    const ids = [...selection.selectedIds];
    selection.deselectAll();
    setIsBulkDeleting(true);
    try {
      const results = await Promise.allSettled(
        ids.map((id) => contractService.delete(id)),
      );
      const failed = results.filter((r) => r.status === 'rejected').length;
      const succeeded = results.length - failed;
      if (failed === 0) {
        toast.success(`Deleted ${succeeded} contract${succeeded === 1 ? '' : 's'}.`);
      } else if (succeeded === 0) {
        toast.error(`Failed to delete ${failed} contract${failed === 1 ? '' : 's'}.`);
      } else {
        toast.info(
          `Deleted ${succeeded}; ${failed} failed. See details on each contract.`,
        );
      }
    } finally {
      setIsBulkDeleting(false);
      refetch();
    }
  };

  if (isLoading) return <ListPageSkeleton />;
  if (error)
    return (
      <ErrorDisplay error={error} title="Failed to load contracts" onRetry={() => refetch()} />
    );

  const handleCreateContract = () => navigate('/contracts/create');

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
        <div className="contract-list-header__actions">
          <div className="contract-list-header__filter">
            <label htmlFor="spec-type-filter" className="contract-list-header__filter-label">
              Spec Type
            </label>
            <select
              id="spec-type-filter"
              value={specTypeFilter}
              onChange={(e) => {
                const value = e.target.value;
                setSearchParams(value ? { spec_type: value } : {}, { replace: true });
                setPage(1);
              }}
              className="contract-list-header__filter-select"
            >
              <option value="">All</option>
              {SPEC_TYPE_OPTIONS.filter(Boolean).map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
          <Button
            variant="secondary"
            onClick={() =>
              exportToCSV(
                contractRows as unknown as Array<Record<string, unknown>>,
                'contracts',
                {
                  columns: [
                    { key: 'id', label: 'ID' },
                    { key: 'name', label: 'Name' },
                    { key: 'original_spec_type', label: 'Spec Type' },
                    { key: 'original_format', label: 'Format' },
                    { key: 'status', label: 'Status' },
                    { key: 'normalization_status', label: 'Normalization' },
                    { key: 'validation_status', label: 'Validation' },
                    { key: 'created_at', label: 'Created' },
                  ],
                },
              )
            }
            data-testid="contracts-export-csv"
          >
            Export CSV
          </Button>
          <Button variant="primary" onClick={handleCreateContract}>
            Create Contract
          </Button>
        </div>
      </div>
      <div className="contract-list-table" data-testid="contract-list-table">
        <table role="table" aria-label="Contracts list">
          <thead>
            <tr>
              <th scope="col" style={{ width: '2.5rem' }}>
                <input
                  type="checkbox"
                  aria-label="Select all DRAFT contracts"
                  checked={selection.isAllSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = selection.isIndeterminate;
                  }}
                  onChange={() => selection.toggleAll()}
                  data-testid="contract-select-all"
                />
              </th>
              <th scope="col">Name</th>
              <th scope="col">Spec Type</th>
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
                onClick={(e) => {
                  if ((e.target as HTMLElement).tagName === 'INPUT') return;
                  navigate(`/contracts/${contract.id}`);
                }}
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
                  <input
                    type="checkbox"
                    aria-label={`Select contract ${contract.name || 'Unnamed'}`}
                    checked={selection.isSelected(contract.id)}
                    disabled={contract.status !== 'DRAFT'}
                    onChange={() => selection.toggle(contract.id)}
                    onClick={(e) => e.stopPropagation()}
                    data-testid={`contract-select-${contract.id}`}
                  />
                </td>
                <td>
                  <strong>{contract.name || 'Unnamed Contract'}</strong>
                </td>
                <td>
                  {contract.original_spec_type ? (
                    <span
                      className={`spec-type-badge spec-type-badge--${contract.original_spec_type.toLowerCase()}`}
                    >
                      {contract.original_spec_type}
                    </span>
                  ) : (
                    '—'
                  )}
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
      <BulkActionBar
        selectedCount={selection.selectedCount}
        onDeselectAll={selection.deselectAll}
        description="Only DRAFT contracts may be bulk-deleted."
        actions={[
          {
            label: `Delete ${selection.selectedCount}`,
            variant: 'danger',
            onClick: handleBulkDelete,
            disabled: isBulkDeleting,
            'data-testid': 'bulk-delete-contracts',
          },
        ]}
      />

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
