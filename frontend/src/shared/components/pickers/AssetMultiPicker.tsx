/**
 * AssetMultiPicker Component
 * Searchable, multi-select picker for choosing multiple assets.
 * Used in ScheduledExportCreatePage (asset_ids), etc.
 * Supports keyboard navigation (ArrowDown, ArrowUp, Enter, Escape).
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useAssets, useAsset } from '../../../features/assets/hooks/useAssets';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { LoadingSpinner } from '../LoadingSpinner';
import { ErrorDisplay } from '../ErrorDisplay';
import { FEATURE_RESOURCE_PICKERS_ENABLED } from '../../config/featureFlags';
import type { Asset } from '../../types/assets';
import './picker-base.css';

const SEARCH_DEBOUNCE_MS = 300;

function SelectedAssetTag({ id, onRemove }: { id: string; onRemove: () => void }) {
  const { data } = useAsset(id);
  const label = data ? `${data.name} (${data.key})` : id.slice(0, 8) + '...';
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

export interface AssetMultiPickerProps {
  value: string[];
  onChange: (assetIds: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
  'data-testid'?: string;
}

export function AssetMultiPicker({
  value,
  onChange,
  placeholder = 'Search and select assets...',
  disabled = false,
  'data-testid': dataTestId = 'asset-multi-picker',
}: AssetMultiPickerProps) {
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
  };

  const { data, isLoading, error, refetch } = useAssets(filters, { enabled: isOpen && FEATURE_RESOURCE_PICKERS_ENABLED });

  const results = data?.results ?? [];
  const maxIndex = results.length - 1;

  const handleToggle = useCallback(
    (asset: Asset) => {
      const isSelected = value.includes(asset.id);
      if (isSelected) {
        onChange(value.filter((id) => id !== asset.id));
      } else {
        onChange([...value, asset.id]);
      }
    },
    [value, onChange]
  );

  const handleRemove = useCallback(
    (assetId: string) => {
      onChange(value.filter((id) => id !== assetId));
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

  if (!FEATURE_RESOURCE_PICKERS_ENABLED) {
    return (
      <div className="asset-multi-picker resource-picker" data-testid={dataTestId}>
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
          placeholder="Enter asset IDs (comma-separated UUIDs)"
          disabled={disabled}
          className="resource-picker-input"
          aria-label="Asset IDs"
        />
      </div>
    );
  }

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
          aria-label="Select assets"
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-activedescendant={
            highlightedIndex >= 0 && results[highlightedIndex]
              ? `asset-multi-picker-option-${results[highlightedIndex].id}`
              : undefined
          }
          role="combobox"
        />
      </div>

      {value.length > 0 && (
        <ul className="resource-picker-selected-tags" data-testid="selected-assets">
          {value.map((id) => (
            <SelectedAssetTag key={id} id={id} onRemove={() => handleRemove(id)} />
          ))}
        </ul>
      )}

      {isOpen && (
        <div className="resource-picker-dropdown" role="listbox" aria-label="Asset options" aria-multiselectable="true">
          {isLoading && (
            <div className="resource-picker-loading">
              <LoadingSpinner size="small" message="Loading assets..." />
            </div>
          )}
          {error && (
            <div className="resource-picker-error">
              <ErrorDisplay
                error={error}
                title="Failed to load assets"
                onRetry={() => refetch()}
              />
            </div>
          )}
          {!isLoading && !error && results.length === 0 && (
            <div className="resource-picker-empty">
              <p>No assets found.</p>
              <Link to="/assets" className="resource-picker-browse-link">
                Browse assets
              </Link>
            </div>
          )}
          {!isLoading && !error && results.length > 0 && (
            <ul className="resource-picker-list" ref={listRef}>
              {results.map((asset: Asset, index: number) => {
                const isSelected = value.includes(asset.id);
                return (
                  <li
                    key={asset.id}
                    id={`asset-multi-picker-option-${asset.id}`}
                    role="option"
                    aria-selected={isSelected}
                    className={`resource-picker-option ${isSelected ? 'selected' : ''} ${index === highlightedIndex ? 'highlighted' : ''}`}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      handleToggle(asset);
                    }}
                    onMouseEnter={() => setHighlightedIndex(index)}
                  >
                    <span className="resource-picker-option-name">{asset.name}</span>
                    <span className="resource-picker-option-meta">
                      {asset.key} {isSelected ? '✓' : ''}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      <p className="resource-picker-hint">
        <Link to="/assets" className="resource-picker-browse-link" data-testid="browse-assets-link">
          Browse assets
        </Link>
        {' '}to find and select assets.
      </p>
    </div>
  );
}
