/**
 * Phase 278.R.7 — Saved Searches management page.
 *
 * Dedicated route at /marketplace/saved-searches for managing all
 * saved searches: view, rename, toggle, delete, and apply filters.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  useSavedSearches,
  useUpdateSavedSearch,
  useDeleteSavedSearch,
} from '../hooks/useSavedSearches';
import type { SavedSearch, ListingListFilters } from '../../../shared/types/marketplace';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { Button } from '../../../shared/components/Button';
import './SavedSearchListPage.css';

export function SavedSearchListPage() {
  const navigate = useNavigate();
  const { data: savedSearches, isLoading, error, refetch } = useSavedSearches();
  const updateMutation = useUpdateSavedSearch();
  const deleteMutation = useDeleteSavedSearch();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleStartRename = (saved: SavedSearch) => {
    setEditingId(saved.id);
    setEditName(saved.name);
  };

  const handleConfirmRename = () => {
    if (!editingId || !editName.trim()) {
      setEditingId(null);
      return;
    }
    updateMutation.mutate(
      { id: editingId, data: { name: editName.trim() } },
      { onSettled: () => setEditingId(null) },
    );
  };

  const handleCancelRename = () => {
    setEditingId(null);
    setEditName('');
  };

  const handleToggleEnabled = (saved: SavedSearch) => {
    updateMutation.mutate({
      id: saved.id,
      data: { enabled: !saved.enabled },
    });
  };

  const handleDelete = (id: string) => {
    deleteMutation.mutate(id, { onSettled: () => setDeletingId(null) });
  };

  const handleApply = (saved: SavedSearch) => {
    const params = new URLSearchParams();
    if (saved.filters.search) params.set('search', String(saved.filters.search));
    if (saved.filters.domain) params.set('domain', String(saved.filters.domain));
    if (saved.filters.pricing_model) params.set('pricing_model', String(saved.filters.pricing_model));
    if (saved.filters.status) params.set('status', String(saved.filters.status));
    if (saved.filters.product_category) params.set('product_category', String(saved.filters.product_category));
    const qs = params.toString();
    navigate(`/marketplace${qs ? `?${qs}` : ''}`);
  };

  const filtersSummary = (filters: ListingListFilters): string => {
    const parts: string[] = [];
    if (filters.search) parts.push(`"${String(filters.search)}"`);
    if (filters.domain) parts.push(String(filters.domain));
    if (filters.pricing_model) parts.push(String(filters.pricing_model));
    if (filters.status) parts.push(String(filters.status));
    if (filters.product_category) parts.push(String(filters.product_category));
    return parts.length > 0 ? parts.join(' · ') : 'No filters';
  };

  const frequencyLabel = (freq: SavedSearch['frequency']): string => {
    if ((freq ?? '') === 'INSTANT') return '—';
    return (freq ?? '').charAt(0) + (freq ?? '').slice(1).toLowerCase();
  };

  if (isLoading) {
    return (
      <div className="saved-search-list-page" data-testid="saved-search-list-page">
        <div className="saved-search-list-header">
          <h1>Saved Searches</h1>
        </div>
        <ListPageSkeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div className="saved-search-list-page" data-testid="saved-search-list-page">
        <div className="saved-search-list-header">
          <h1>Saved Searches</h1>
        </div>
        <ErrorDisplay
          error={error}
          title="Failed to load saved searches"
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  if (!savedSearches || savedSearches.length === 0) {
    return (
      <div className="saved-search-list-page" data-testid="saved-search-list-page">
        <div className="saved-search-list-header">
          <h1>Saved Searches</h1>
        </div>
        <EmptyState
          title="No saved searches"
          message="Save your marketplace filters to quickly re-apply them later. Use the bookmark button in the marketplace filter bar to create one."
          action={{ label: 'Browse Marketplace', onClick: () => navigate('/marketplace') }}
        />
      </div>
    );
  }

  return (
    <div className="saved-search-list-page" data-testid="saved-search-list-page">
      <div className="saved-search-list-header">
        <h1>Saved Searches</h1>
        <span className="saved-search-count">{savedSearches.length} saved</span>
      </div>

      <div className="saved-search-table" data-testid="saved-search-table">
        <div className="saved-search-table-header">
          <span className="sst-col-name">Name</span>
          <span className="sst-col-filters">Filters</span>
          <span className="sst-col-frequency">Alert</span>
          <span className="sst-col-matches">Matches</span>
          <span className="sst-col-actions">Actions</span>
        </div>

        {savedSearches.map((saved) => (
          <div
            key={saved.id}
            className={`saved-search-row${!saved.enabled ? ' saved-search-row-disabled' : ''}`}
            data-testid={`saved-search-row-${saved.id}`}
          >
            <span className="sst-col-name">
              {editingId === saved.id ? (
                <span className="saved-search-inline-edit">
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleConfirmRename();
                      if (e.key === 'Escape') handleCancelRename();
                    }}
                    className="saved-search-rename-input"
                    autoFocus
                    data-testid={`rename-input-${saved.id}`}
                  />
                  <button
                    className="saved-search-rename-confirm"
                    onClick={handleConfirmRename}
                    aria-label="Confirm rename"
                  >
                    ✓
                  </button>
                  <button
                    className="saved-search-rename-cancel"
                    onClick={handleCancelRename}
                    aria-label="Cancel rename"
                  >
                    ✕
                  </button>
                </span>
              ) : (
                <span className="saved-search-row-name">
                  <span
                    className="saved-search-name-text"
                    onDoubleClick={() => handleStartRename(saved)}
                    title="Double-click to rename"
                  >
                    {saved.name}
                  </span>
                  <button
                    className="saved-search-rename-trigger"
                    onClick={() => handleStartRename(saved)}
                    aria-label={`Rename ${saved.name}`}
                    title="Rename"
                  >
                    ✎
                  </button>
                </span>
              )}
            </span>

            <span className="sst-col-filters">
              <code className="saved-search-filters-summary">{filtersSummary(saved.filters)}</code>
            </span>

            <span className="sst-col-frequency">
              <label className="saved-search-toggle-label">
                <input
                  type="checkbox"
                  checked={saved.enabled}
                  onChange={() => handleToggleEnabled(saved)}
                  className="saved-search-enabled-toggle"
                  aria-label={`${saved.enabled ? 'Disable' : 'Enable'} ${saved.name}`}
                />
                <span className="saved-search-frequency-badge">
                  {frequencyLabel(saved.frequency)}
                </span>
              </label>
            </span>

            <span className="sst-col-matches">
              {saved.last_matched_count != null ? (
                <span className="saved-search-match-count">
                  {saved.last_matched_count}
                  {saved.last_triggered_at && (
                    <span className="saved-search-match-time">
                      {' '}
                      {new Date(saved.last_triggered_at).toLocaleDateString()}
                    </span>
                  )}
                </span>
              ) : (
                <span className="saved-search-no-matches">—</span>
              )}
            </span>

            <span className="sst-col-actions">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => handleApply(saved)}
                aria-label={`Apply filters from ${saved.name}`}
              >
                Apply
              </Button>
              {deletingId === saved.id ? (
                <span className="saved-search-delete-confirm">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleDelete(saved.id)}
                    aria-label={`Confirm delete ${saved.name}`}
                  >
                    Delete
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setDeletingId(null)}
                    aria-label="Cancel delete"
                  >
                    Cancel
                  </Button>
                </span>
              ) : (
                <button
                  className="saved-search-delete-icon-btn"
                  onClick={() => setDeletingId(saved.id)}
                  aria-label={`Delete ${saved.name}`}
                  title="Delete"
                >
                  🗑
                </button>
              )}
            </span>
          </div>
        ))}
      </div>

      <div className="saved-search-list-footer">
        <Button variant="secondary" onClick={() => navigate('/marketplace')}>
          ← Back to Marketplace
        </Button>
      </div>
    </div>
  );
}
