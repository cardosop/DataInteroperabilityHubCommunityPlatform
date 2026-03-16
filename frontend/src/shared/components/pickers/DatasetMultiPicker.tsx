/**
 * DatasetMultiPicker Component
 * Searchable, multi-select picker for choosing multiple datasets.
 * Used in ScheduledExportCreatePage (dataset_ids), etc.
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

function SelectedDatasetTag({ id, onRemove }: { id: string; onRemove: () => void }) {
  const { data } = useDataset(id);
  const label = data ? `${data.name} (${data.format})` : id.slice(0, 8) + '...';
  return (
    <li className="resource-picker-tag">
      <span>{label}</span>
      <button
        type="button"
        onClick={onRemove}
        className="resource-picker-tag-remove"
        aria-label={`Remove ${label}`}
      >
        ×
      </button>
    </li>
  );
}

export interface DatasetMultiPickerProps {
  value: string[];
  onChange: (datasetIds: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
  assetId?: string;
  'data-testid'?: string;
}

export function DatasetMultiPicker({
  value,
  onChange,
  placeholder = 'Search and select datasets...',
  disabled = false,
  assetId,
  'data-testid': dataTestId = 'dataset-multi-picker',
}: DatasetMultiPickerProps) {
  if (!FEATURE_RESOURCE_PICKERS_ENABLED) {
    return (
      <div className="dataset-multi-picker resource-picker" data-testid={dataTestId}>
        <input
          type="text"
          value={value.join(', ')}
          onChange={(e) =>
            onChange(
              e.target.value
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean)
            )
          }
          placeholder="Enter dataset IDs (comma-separated UUIDs)"
          disabled={disabled}
          className="resource-picker-input"
          aria-label="Dataset IDs"
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

  const handleToggle = useCallback(
    (dataset: Dataset) => {
      const isSelected = value.includes(dataset.id);
      if (isSelected) {
        onChange(value.filter((id) => id !== dataset.id));
      } else {
        onChange([...value, dataset.id]);
      }
    },
    [value, onChange]
  );

  const handleRemove = useCallback(
    (datasetId: string) => {
      onChange(value.filter((id) => id !== datasetId));
    },
    [value, onChange]
  );

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
          handleToggle(results[highlightedIndex]);
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
          value={isOpen ? searchInput : ''}
          onChange={(e) => {
            setSearchInput(e.target.value);
            setPage(1);
            if (!isOpen) setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onBlur={() => setTimeout(() => setIsOpen(false), 200)}
          onKeyDown={handleKeyDown}
          placeholder={value.length === 0 ? placeholder : undefined}
          disabled={disabled}
          className="resource-picker-input"
          aria-label="Select datasets"
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-activedescendant={
            highlightedIndex >= 0 && results[highlightedIndex]
              ? `dataset-multi-picker-option-${results[highlightedIndex].id}`
              : undefined
          }
          role="combobox"
        />
      </div>

      {value.length > 0 && (
        <ul className="resource-picker-selected-tags" data-testid="selected-datasets">
          {value.map((id) => (
            <SelectedDatasetTag key={id} id={id} onRemove={() => handleRemove(id)} />
          ))}
        </ul>
      )}

      {isOpen && (
        <div className="resource-picker-dropdown" role="listbox" aria-label="Dataset options" aria-multiselectable="true">
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
              {results.map((dataset: Dataset, index: number) => {
                const isSelected = value.includes(dataset.id);
                return (
                  <li
                    key={dataset.id}
                    id={`dataset-multi-picker-option-${dataset.id}`}
                    role="option"
                    aria-selected={isSelected}
                    className={`resource-picker-option ${isSelected ? 'selected' : ''} ${index === highlightedIndex ? 'highlighted' : ''}`}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      handleToggle(dataset);
                    }}
                    onMouseEnter={() => setHighlightedIndex(index)}
                  >
                    <span className="resource-picker-option-name">{dataset.name}</span>
                    <span className="resource-picker-option-meta">
                      {dataset.format} {isSelected ? '✓' : ''}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      <p className="resource-picker-hint">
        <Link to="/datasets" className="resource-picker-browse-link" data-testid="browse-datasets-link">
          Browse datasets
        </Link>
        {' '}to find and select datasets.
      </p>
    </div>
  );
}
