/**
 * DatasetPicker Component
 * Searchable, single-select picker for choosing an existing dataset.
 * Used in AssetDetailPage (attach dataset), DQ Run, Compliance Run, etc.
 * Supports keyboard navigation (ArrowDown, ArrowUp, Enter, Escape).
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useDatasets, useDataset } from '../../../features/datasets/hooks/useDatasets';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { LoadingSpinner } from '../LoadingSpinner';
import { ErrorDisplay } from '../ErrorDisplay';
import { FEATURE_RESOURCE_PICKERS_ENABLED } from '../../config/featureFlags';
import type { Dataset } from '../../types/datasets';
import './picker-base.css';

const SEARCH_DEBOUNCE_MS = 300;

export interface DatasetPickerProps {
  value: string | null;
  onChange: (datasetId: string | null) => void;
  placeholder?: string;
  disabled?: boolean;
  /** Filter by asset_id when linking to a specific asset */
  assetId?: string;
  'data-testid'?: string;
}

export function DatasetPicker({
  value,
  onChange,
  placeholder = 'Search and select a dataset...',
  disabled = false,
  assetId,
  'data-testid': dataTestId = 'dataset-picker',
}: DatasetPickerProps) {
  if (!FEATURE_RESOURCE_PICKERS_ENABLED) {
    return (
      <div className="dataset-picker resource-picker" data-testid={dataTestId}>
        <input
          type="text"
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value.trim() || null)}
          placeholder="Enter dataset ID (UUID)"
          disabled={disabled}
          className="resource-picker-input"
          aria-label="Dataset ID"
        />
      </div>
    );
  }

  const [searchInput, setSearchInput] = useState('');
  const debouncedSearch = useDebouncedValue(searchInput, SEARCH_DEBOUNCE_MS);
  const [isOpen, setIsOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const listRef = useRef<HTMLUListElement>(null);

  const filters = {
    page,
    page_size: 20,
    search: debouncedSearch || undefined,
    ordering: '-created_at',
    asset_id: assetId,
  };

  const { data, isLoading, error, refetch } = useDatasets(filters, { enabled: isOpen });

  const results = data?.results ?? [];
  const maxIndex = results.length - 1;

  const handleSelect = useCallback(
    (dataset: Dataset) => {
      onChange(dataset.id);
      setIsOpen(false);
      setSearchInput('');
      setHighlightedIndex(-1);
    },
    [onChange]
  );

  const handleClear = useCallback(() => {
    onChange(null);
    setIsOpen(false);
    setSearchInput('');
    setHighlightedIndex(-1);
  }, [onChange]);

  const selectedFromList = value ? results.find((d: Dataset) => d.id === value) : null;
  const { data: selectedDatasetData } = useDataset(value);
  const selectedDataset =
    selectedFromList ?? (value && selectedDatasetData ? selectedDatasetData : null);

  useEffect(() => {
    setHighlightedIndex(-1);
  }, [debouncedSearch, results.length]);

  useEffect(() => {
    if (highlightedIndex >= 0 && listRef.current) {
      const option = listRef.current.children[highlightedIndex] as HTMLElement;
      option?.scrollIntoView({ block: 'nearest' });
    }
  }, [highlightedIndex]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        setIsOpen(true);
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightedIndex((i) => (i < maxIndex ? i + 1 : 0));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightedIndex((i) => (i > 0 ? i - 1 : maxIndex));
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightedIndex >= 0 && results[highlightedIndex]) {
          handleSelect(results[highlightedIndex]);
        }
        break;
      case 'Escape':
        e.preventDefault();
        setIsOpen(false);
        setHighlightedIndex(-1);
        break;
      default:
        break;
    }
  };

  return (
    <div className="resource-picker" data-testid={dataTestId}>
      <div className="resource-picker-trigger">
        <input
          type="text"
          value={
            isOpen
              ? searchInput
              : selectedDataset
                ? `${selectedDataset.name} (${selectedDataset.format})`
                : ''
          }
          onChange={(e) => {
            setSearchInput(e.target.value);
            setPage(1);
            if (!isOpen) setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onBlur={() => setTimeout(() => setIsOpen(false), 200)}
          onKeyDown={handleKeyDown}
          placeholder={value ? undefined : placeholder}
          disabled={disabled}
          className="resource-picker-input"
          aria-label="Select dataset"
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-activedescendant={
            highlightedIndex >= 0 && results[highlightedIndex]
              ? `dataset-picker-option-${results[highlightedIndex].id}`
              : undefined
          }
          role="combobox"
        />
        {value && (
          <button
            type="button"
            onClick={handleClear}
            className="resource-picker-clear"
            aria-label="Clear selection"
          >
            ×
          </button>
        )}
      </div>

      {isOpen && (
        <div className="resource-picker-dropdown" role="listbox" aria-label="Dataset options">
          {isLoading && (
            <div className="resource-picker-loading">
              <LoadingSpinner size="small" message="Loading datasets..." />
            </div>
          )}
          {error && (
            <div className="resource-picker-error">
              <ErrorDisplay
                error={error}
                title="Failed to load datasets"
                onRetry={() => refetch()}
              />
            </div>
          )}
          {!isLoading && !error && results.length === 0 && (
            <div className="resource-picker-empty">
              <p>No datasets found.</p>
              <Link to="/datasets" className="resource-picker-browse-link">
                Browse datasets
              </Link>
            </div>
          )}
          {!isLoading && !error && results.length > 0 && (
            <ul className="resource-picker-list" ref={listRef}>
              {results.map((dataset: Dataset, index: number) => (
                <li
                  key={dataset.id}
                  id={`dataset-picker-option-${dataset.id}`}
                  role="option"
                  aria-selected={value === dataset.id}
                  className={`resource-picker-option ${value === dataset.id ? 'selected' : ''} ${index === highlightedIndex ? 'highlighted' : ''}`}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    handleSelect(dataset);
                  }}
                  onMouseEnter={() => setHighlightedIndex(index)}
                >
                  <span className="resource-picker-option-name">{dataset.name}</span>
                  <span className="resource-picker-option-meta">{dataset.format}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <p className="resource-picker-hint">
        <Link to="/datasets" className="resource-picker-browse-link" data-testid="browse-datasets-link">
          Browse datasets
        </Link>
        {' '}to find and select a dataset.
      </p>
    </div>
  );
}
