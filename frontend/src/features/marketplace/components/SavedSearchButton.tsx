/**
 * Phase 278.H.4 — Saved search button + dropdown.
 *
 * "Save current filters" action with a dropdown listing existing
 * saved searches. Clicking a saved search applies its filters.
 */
import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSavedSearches, useCreateSavedSearch, useDeleteSavedSearch } from '../hooks/useSavedSearches';
import type { ListingListFilters, SavedSearch, SavedSearchCreateRequest } from '../../../shared/types/marketplace';
import {
  emitUxActivationEvent,
  type SavedSearchDetail,
} from '../../../shared/telemetry/uxActivationTelemetry';
import './SavedSearchButton.css';

interface SavedSearchButtonProps {
  currentFilters: ListingListFilters;
  onApply: (filters: ListingListFilters) => void;
}

export function SavedSearchButton({ currentFilters, onApply }: SavedSearchButtonProps) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [nameInput, setNameInput] = useState('');
  const [showNameInput, setShowNameInput] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const { data: savedSearches } = useSavedSearches();
  const createMutation = useCreateSavedSearch();
  const deleteMutation = useDeleteSavedSearch();

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setShowNameInput(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSave = () => {
    if (!nameInput.trim()) return;
    const { page, page_size, ...filterData } = currentFilters;
    const name = nameInput.trim();
    createMutation.mutate({
      name,
      query: '',
      filters: filterData as unknown as Record<string, unknown>,
      frequency: 'INSTANT',
    } as SavedSearchCreateRequest);
    emitUxActivationEvent('meshant.saved_search.created', {
      search_name: name,
      has_filters: hasActiveFilters,
      frequency: 'INSTANT',
    } satisfies SavedSearchDetail);
    setNameInput('');
    setShowNameInput(false);
  };

  const handleApply = (saved: SavedSearch) => {
    emitUxActivationEvent('meshant.saved_search.applied', {
      search_id: saved.id,
      search_name: saved.name,
      has_filters: true,
      frequency: saved.frequency,
    } satisfies SavedSearchDetail);
    onApply({ ...saved.filters, page: 1 });
    setOpen(false);
  };

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    const saved = savedSearches?.find((s) => s.id === id);
    emitUxActivationEvent('meshant.saved_search.deleted', {
      search_id: id,
      search_name: saved?.name,
      has_filters: false,
    } satisfies SavedSearchDetail);
    deleteMutation.mutate(id);
  };

  const hasActiveFilters = !!(
    currentFilters.search ||
    currentFilters.domain ||
    currentFilters.pricing_model ||
    currentFilters.status ||
    currentFilters.product_category
  );

  return (
    <div className="saved-search-btn-wrapper" ref={ref} data-testid="saved-search-wrapper">
      <button
        className="filter-btn saved-search-trigger"
        onClick={() => setOpen(!open)}
        aria-label="Saved searches"
        title="Saved searches"
      >
        🔖
      </button>

      {open && (
        <div className="saved-search-dropdown" data-testid="saved-search-dropdown">
          <div className="saved-search-dropdown-header">
            <h4>Saved Searches</h4>
          </div>

          {hasActiveFilters && (
            <div className="saved-search-save-section">
              {showNameInput ? (
                <div className="saved-search-name-row">
                  <input
                    type="text"
                    value={nameInput}
                    onChange={(e) => setNameInput(e.target.value)}
                    placeholder="Search name..."
                    className="saved-search-name-input"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleSave();
                      if (e.key === 'Escape') {
                        setShowNameInput(false);
                        setNameInput('');
                      }
                    }}
                  />
                  <button className="saved-search-save-confirm" onClick={handleSave}>
                    Save
                  </button>
                  <button
                    className="saved-search-save-cancel"
                    onClick={() => {
                      setShowNameInput(false);
                      setNameInput('');
                    }}
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <button
                  className="saved-search-save-btn"
                  onClick={() => setShowNameInput(true)}
                >
                  + Save current filters
                </button>
              )}
            </div>
          )}

          <div className="saved-search-list">
            {(!savedSearches || savedSearches.length === 0) && (
              <p className="saved-search-empty">No saved searches yet.</p>
            )}
            {savedSearches?.map((saved) => (
              <div
                key={saved.id}
                className="saved-search-item"
                onClick={() => handleApply(saved)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleApply(saved);
                }}
              >
                <span className="saved-search-item-name">{saved.name}</span>
                <span className="saved-search-item-freq">
                  {(saved.frequency ?? '') === 'INSTANT' ? '' : (saved.frequency ?? '').toLowerCase()}
                </span>
                <button
                  className="saved-search-delete-btn"
                  onClick={(e) => handleDelete(e, saved.id)}
                  aria-label={`Delete ${saved.name}`}
                  title="Delete"
                >
                  🗑
                </button>
              </div>
            ))}
          </div>

          <div className="saved-search-dropdown-footer">
            <button
              className="saved-search-manage-link"
              onClick={() => {
                navigate('/marketplace/saved-searches');
                setOpen(false);
              }}
            >
              Manage all →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
