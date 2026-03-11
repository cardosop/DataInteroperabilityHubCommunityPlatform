/**
 * AssetPicker Component
 * Searchable, single-select picker for choosing an existing asset.
 * Used in DatasetCreatePage and other flows requiring asset selection.
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
import './AssetPicker.css';

const SEARCH_DEBOUNCE_MS = 300;

export interface AssetPickerProps {
  value: string | null;
  onChange: (assetId: string | null) => void;
  placeholder?: string;
  disabled?: boolean;
  'data-testid'?: string;
}

export function AssetPicker({
  value,
  onChange,
  placeholder = 'Search and select an asset...',
  disabled = false,
  'data-testid': dataTestId = 'asset-picker',
}: AssetPickerProps) {
  if (!FEATURE_RESOURCE_PICKERS_ENABLED) {
    return (
      <div className="asset-picker" data-testid={dataTestId}>
        <input
          type="text"
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value.trim() || null)}
          placeholder="Enter asset ID (UUID)"
          disabled={disabled}
          className="asset-picker-input"
          aria-label="Asset ID"
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
  };

  const { data, isLoading, error, refetch } = useAssets(filters, { enabled: isOpen });

  const results = data?.results ?? [];
  const maxIndex = results.length - 1;

  const handleSelect = useCallback(
    (asset: Asset) => {
      onChange(asset.id);
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

  const selectedFromList = value ? results.find((a: Asset) => a.id === value) : null;
  const { data: selectedAssetData } = useAsset(value);
  const selectedAsset = selectedFromList ?? (value && selectedAssetData ? selectedAssetData : null);

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
    <div className="asset-picker" data-testid={dataTestId}>
      <div className="asset-picker-trigger">
        <input
          type="text"
          value={isOpen ? searchInput : selectedAsset ? `${selectedAsset.name} (${selectedAsset.key})` : ''}
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
          className="asset-picker-input"
          aria-label="Select asset"
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-activedescendant={
            highlightedIndex >= 0 && results[highlightedIndex]
              ? `asset-picker-option-${results[highlightedIndex].id}`
              : undefined
          }
          role="combobox"
        />
        {value && (
          <button
            type="button"
            onClick={handleClear}
            className="asset-picker-clear"
            aria-label="Clear selection"
          >
            ×
          </button>
        )}
      </div>

      {isOpen && (
        <div
          className="asset-picker-dropdown"
          role="listbox"
          aria-label="Asset options"
        >
          {isLoading && (
            <div className="asset-picker-loading">
              <LoadingSpinner size="small" message="Loading assets..." />
            </div>
          )}
          {error && (
            <div className="asset-picker-error">
              <ErrorDisplay
                error={error}
                title="Failed to load assets"
                onRetry={() => refetch()}
              />
            </div>
          )}
          {!isLoading && !error && results.length === 0 && (
            <div className="asset-picker-empty">
              <p>No assets found.</p>
              <Link to="/assets" className="asset-picker-browse-link">
                Browse assets
              </Link>
            </div>
          )}
          {!isLoading && !error && results.length > 0 && (
            <ul className="asset-picker-list" ref={listRef}>
              {results.map((asset: Asset, index: number) => (
                <li
                  key={asset.id}
                  id={`asset-picker-option-${asset.id}`}
                  role="option"
                  aria-selected={value === asset.id}
                  className={`asset-picker-option ${value === asset.id ? 'selected' : ''} ${index === highlightedIndex ? 'highlighted' : ''}`}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    handleSelect(asset);
                  }}
                  onMouseEnter={() => setHighlightedIndex(index)}
                >
                  <span className="asset-picker-option-name">{asset.name}</span>
                  <span className="asset-picker-option-key">{asset.key}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <p className="asset-picker-hint">
        <Link to="/assets" className="asset-picker-browse-link" data-testid="browse-assets-link">
          Browse assets
        </Link>
        {' '}to find and select an asset for linking.
      </p>
    </div>
  );
}
