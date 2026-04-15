/**
 * Asset List Page
 * Displays list of assets with filtering and pagination
 */

import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { BulkActionBar } from '../../../shared/components/BulkActionBar';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { useToast } from '../../../shared/components/Toast';
import { useBulkSelection } from '../../../shared/hooks/useBulkSelection';
import { exportToCSV } from '../../../shared/utils/exportUtils';
import type { AssetStatus, AssetVisibility } from '../../../shared/types/assets';
import { assetService } from '../services/assetService';
import { useAssets } from '../hooks/useAssets';
import './AssetListPage.css';
import { Button } from '../../../shared/components/Button';

const ALLOWED_STATUSES: AssetStatus[] = ['DRAFT', 'ACTIVE', 'RETIRED'];
const ALLOWED_VISIBILITIES: AssetVisibility[] = ['INTERNAL', 'EXTERNAL', 'PUBLIC'];
const ALLOWED_DQ = ['PASSED', 'FAILED', 'WARNING', 'PENDING'];
const ALLOWED_COMPLIANCE = ['COMPLIANT', 'NON_COMPLIANT', 'WARNING', 'PENDING'];

function pickParam<T extends string>(value: string | null, allowed: readonly T[]): T | '' {
  return value && (allowed as readonly string[]).includes(value) ? (value as T) : '';
}

export function AssetListPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [search, setSearch] = useState(() => searchParams.get('search') ?? '');
  const [domainFilter, setDomainFilter] = useState<string>(() => searchParams.get('domain') ?? '');
  const [statusFilter, setStatusFilter] = useState<AssetStatus | ''>(
    () => pickParam(searchParams.get('status'), ALLOWED_STATUSES),
  );
  const [visibilityFilter, setVisibilityFilter] = useState<AssetVisibility | ''>(
    () => pickParam(searchParams.get('visibility'), ALLOWED_VISIBILITIES),
  );
  const [dqStatusFilter, setDqStatusFilter] = useState(
    () => pickParam(searchParams.get('dq_status'), ALLOWED_DQ),
  );
  const [complianceStatusFilter, setComplianceStatusFilter] = useState(
    () => pickParam(searchParams.get('compliance_status'), ALLOWED_COMPLIANCE),
  );

  const filters = {
    page,
    page_size: pageSize,
    search: search || undefined,
    domain: domainFilter || undefined,
    status: statusFilter || undefined,
    visibility: visibilityFilter || undefined,
    dq_status: dqStatusFilter || undefined,
    compliance_status: complianceStatusFilter || undefined,
    ordering: '-created_at',
  };

  const { data, isLoading, error, refetch } = useAssets(filters);
  const toast = useToast();
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);

  const assetRows = data?.results ?? [];
  // DRAFT-only bulk delete: guards against catastrophic removal of ACTIVE
  // assets that may be under active consumer use. The backend will also
  // reject non-DRAFT deletes, but disabling the checkbox is the right UX.
  const selection = useBulkSelection({
    allIds: assetRows.map((a) => a.id),
    isSelectable: (id) => assetRows.find((r) => r.id === id)?.status === 'DRAFT',
  });

  const handleAssetClick = (assetId: string) => {
    navigate(`/assets/${assetId}`);
  };

  const handleBulkDelete = async () => {
    if (selection.selectedIds.length === 0) return;
    const count = selection.selectedIds.length;
    const ok = window.confirm(
      `Delete ${count} DRAFT asset${count === 1 ? '' : 's'}? This cannot be undone.`,
    );
    if (!ok) return;
    // Use the raw service directly — not `useDeleteAsset`, which fires one
    // "Asset deleted" toast per call. For bulk, we want ONE summary toast.
    // Parallel deletes: each DELETE hits its own row, ordering is not
    // meaningful; `allSettled` surfaces partial failures in a single await.
    const ids = [...selection.selectedIds];
    selection.deselectAll();
    setIsBulkDeleting(true);
    try {
      const results = await Promise.allSettled(
        ids.map((id) => assetService.delete(id)),
      );
      const failed = results.filter((r) => r.status === 'rejected').length;
      const succeeded = results.length - failed;
      if (failed === 0) {
        toast.success(`Deleted ${succeeded} asset${succeeded === 1 ? '' : 's'}.`);
      } else if (succeeded === 0) {
        toast.error(`Failed to delete ${failed} asset${failed === 1 ? '' : 's'}.`);
      } else {
        toast.info(
          `Deleted ${succeeded}; ${failed} failed. See details on each asset.`,
        );
      }
    } finally {
      setIsBulkDeleting(false);
      refetch();
    }
  };

  const handleCreateAsset = () => {
    navigate('/assets/create');
  };

  if (isLoading) {
    return <ListPageSkeleton />;
  }

  if (error) {
    return (
      <div className="asset-list-error-wrapper">
        <ErrorDisplay error={error} title="Failed to load assets" onRetry={() => refetch()} />
        <div className="asset-list-error-actions">
          <Button variant="primary" onClick={handleCreateAsset}>
            Create Asset
          </Button>
        </div>
      </div>
    );
  }

  if (!data || data.results.length === 0) {
    return (
      <EmptyState
        data-testid="asset-list-empty-state"
        title="No assets found"
        message={
          search || domainFilter || statusFilter || visibilityFilter
            ? 'Try adjusting your filters to see more results.'
            : 'Get started by creating your first asset.'
        }
        action={
          !search && !domainFilter && !statusFilter && !visibilityFilter
            ? { label: 'Create Asset', onClick: handleCreateAsset }
            : undefined
        }
      />
    );
  }

  return (
    <div className="asset-list-page" data-testid="asset-list-page">
      <div className="asset-list-header" data-testid="asset-list-header">
        <h1>Assets</h1>
        <div className="asset-list-header-actions">
          <Button
            variant="secondary"
            onClick={() =>
              exportToCSV(
                assetRows as unknown as Array<Record<string, unknown>>,
                'assets',
                {
                  columns: [
                    { key: 'id', label: 'ID' },
                    { key: 'name', label: 'Name' },
                    { key: 'key', label: 'Key' },
                    { key: 'domain', label: 'Domain' },
                    { key: 'status', label: 'Status' },
                    { key: 'visibility', label: 'Visibility' },
                    { key: 'dq_status', label: 'DQ Status' },
                    { key: 'compliance_status', label: 'Compliance Status' },
                    { key: 'created_at', label: 'Created' },
                  ],
                },
              )
            }
            data-testid="assets-export-csv"
          >
            Export CSV
          </Button>
          <Button variant="primary" onClick={handleCreateAsset}>
            Create Asset
          </Button>
        </div>
      </div>

      <div className="asset-list-filters" role="group" aria-label="Asset filters" data-testid="asset-list-filters">
        <label htmlFor="asset-search" className="sr-only">
          Search assets
        </label>
        <input
          id="asset-search"
          type="text"
          placeholder="Search assets..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="filter-input"
          aria-label="Search assets"
        />
        <label htmlFor="asset-domain-filter" className="sr-only">
          Filter by domain
        </label>
        <select
          id="asset-domain-filter"
          value={domainFilter}
          onChange={(e) => {
            setDomainFilter(e.target.value);
            setPage(1);
          }}
          className="filter-select"
          aria-label="Filter by domain"
        >
          <option value="">All Domains</option>
          {/* Domain options would be populated from backend or extracted from existing assets */}
        </select>
        <label htmlFor="asset-status-filter" className="sr-only">
          Filter by status
        </label>
        <select
          id="asset-status-filter"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as AssetStatus | '');
            setPage(1);
          }}
          className="filter-select"
          aria-label="Filter by status"
        >
          <option value="">All Statuses</option>
          <option value="DRAFT">Draft</option>
          <option value="ACTIVE">Active</option>
          <option value="RETIRED">Retired</option>
        </select>
        <label htmlFor="asset-visibility-filter" className="sr-only">
          Filter by visibility
        </label>
        <select
          id="asset-visibility-filter"
          value={visibilityFilter}
          onChange={(e) => {
            setVisibilityFilter(e.target.value as AssetVisibility | '');
            setPage(1);
          }}
          className="filter-select"
          aria-label="Filter by visibility"
        >
          <option value="">All Visibilities</option>
          <option value="INTERNAL">Internal</option>
          <option value="EXTERNAL">External</option>
          <option value="PUBLIC">Public</option>
        </select>
        <select
          value={dqStatusFilter}
          onChange={(e) => { setDqStatusFilter(e.target.value); setPage(1); }}
          className="filter-select"
          aria-label="Filter by DQ status"
        >
          <option value="">All DQ</option>
          <option value="PASSED">Passed</option>
          <option value="FAILED">Failed</option>
          <option value="WARNING">Warning</option>
          <option value="PENDING">Pending</option>
        </select>
        <select
          value={complianceStatusFilter}
          onChange={(e) => { setComplianceStatusFilter(e.target.value); setPage(1); }}
          className="filter-select"
          aria-label="Filter by compliance status"
        >
          <option value="">All Compliance</option>
          <option value="COMPLIANT">Compliant</option>
          <option value="NON_COMPLIANT">Non-Compliant</option>
          <option value="WARNING">Warning</option>
          <option value="PENDING">Pending</option>
        </select>
      </div>

      <div className="asset-list-table" data-testid="asset-list-table">
        <table role="table" aria-label="Assets list">
          <thead>
            <tr>
              <th scope="col" style={{ width: '2.5rem' }}>
                <input
                  type="checkbox"
                  aria-label="Select all DRAFT assets"
                  checked={selection.isAllSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = selection.isIndeterminate;
                  }}
                  onChange={() => selection.toggleAll()}
                  data-testid="asset-select-all"
                />
              </th>
              <th scope="col">Name</th>
              <th scope="col">Key</th>
              <th scope="col">Domain</th>
              <th scope="col">Status</th>
              <th scope="col">Visibility</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((asset) => (
              <tr
                key={asset.id}
                data-asset-id={asset.id}
                onClick={(e) => {
                  if ((e.target as HTMLElement).tagName === 'INPUT') return;
                  handleAssetClick(asset.id);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleAssetClick(asset.id);
                  }
                }}
                className="asset-row"
                role="row"
                tabIndex={0}
                aria-label={`Asset ${asset.name}`}
              >
                <td>
                  <input
                    type="checkbox"
                    aria-label={`Select asset ${asset.name}`}
                    checked={selection.isSelected(asset.id)}
                    disabled={asset.status !== 'DRAFT'}
                    onChange={() => selection.toggle(asset.id)}
                    onClick={(e) => e.stopPropagation()}
                    data-testid={`asset-select-${asset.id}`}
                  />
                </td>
                <td>
                  <strong>{asset.name}</strong>
                  {asset.description && (
                    <div className="asset-description">{asset.description}</div>
                  )}
                </td>
                <td>
                  <code>{asset.key}</code>
                </td>
                <td>{asset.domain || '-'}</td>
                <td>
                  <span
                    className={`status-badge status-${asset.status.toLowerCase()}`}
                    aria-label={`Status: ${asset.status}`}
                  >
                    {asset.status}
                  </span>
                </td>
                <td>
                  <span
                    className={`visibility-badge visibility-${asset.visibility.toLowerCase()}`}
                    aria-label={`Visibility: ${asset.visibility}`}
                  >
                    {asset.visibility}
                  </span>
                </td>
                <td>{new Date(asset.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <BulkActionBar
        selectedCount={selection.selectedCount}
        onDeselectAll={selection.deselectAll}
        description="Only DRAFT assets may be bulk-deleted."
        actions={[
          {
            label: `Delete ${selection.selectedCount}`,
            variant: 'danger',
            onClick: handleBulkDelete,
            disabled: isBulkDeleting,
            'data-testid': 'bulk-delete-assets',
          },
        ]}
      />

      {data.total_pages > 1 && (
        <div className="asset-list-pagination">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={!data.has_previous}
            type="button"
          >
            Previous
          </button>
          <span>
            Page {data.page} of {data.total_pages} ({data.count} total)
          </span>
          <button
            onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
            disabled={!data.has_next}
            type="button"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
