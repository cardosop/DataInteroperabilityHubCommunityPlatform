/**
 * FilePicker Component
 * Searchable, single-select picker for choosing an existing file.
 * Used in DQ Run, Compliance Run, Access Request, etc.
 * Supports keyboard navigation (ArrowDown, ArrowUp, Enter, Escape).
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useFiles, useFile } from '../../../features/files/hooks/useFiles';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { LoadingSpinner } from '../LoadingSpinner';
import { ErrorDisplay } from '../ErrorDisplay';
import { FEATURE_RESOURCE_PICKERS_ENABLED } from '../../config/featureFlags';
import type { File as FileItem } from '../../types/files';
import './picker-base.css';

const SEARCH_DEBOUNCE_MS = 300;

export interface FilePickerProps {
  value: string | null;
  onChange: (fileId: string | null) => void;
  placeholder?: string;
  disabled?: boolean;
  /** Filter by asset_id or dataset_id when scoping to a resource. Note: backend files API does not yet support these; passed for future use. */
  assetId?: string;
  datasetId?: string;
  'data-testid'?: string;
}

export function FilePicker({
  value,
  onChange,
  placeholder = 'Search and select a file...',
  disabled = false,
  assetId,
  datasetId,
  'data-testid': dataTestId = 'file-picker',
}: FilePickerProps) {
  if (!FEATURE_RESOURCE_PICKERS_ENABLED) {
    return (
      <div className="file-picker resource-picker" data-testid={dataTestId}>
        <input
          type="text"
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value.trim() || null)}
          placeholder="Enter file ID (UUID)"
          disabled={disabled}
          className="resource-picker-input"
          aria-label="File ID"
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
    dataset_id: datasetId,
  };

  const { data, isLoading, error, refetch } = useFiles(filters, { enabled: isOpen });

  const results = data?.results ?? [];
  const maxIndex = results.length - 1;

  const handleSelect = useCallback(
    (file: FileItem) => {
      onChange(file.id);
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

  const selectedFromList = value ? results.find((f: FileItem) => f.id === value) : null;
  const { data: selectedFileData } = useFile(value);
  const selectedFile = selectedFromList ?? (value && selectedFileData ? selectedFileData : null);

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
              : selectedFile
                ? `${selectedFile.name} (${selectedFile.content_type})`
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
          aria-label="Select file"
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-activedescendant={
            highlightedIndex >= 0 && results[highlightedIndex]
              ? `file-picker-option-${results[highlightedIndex].id}`
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
        <div className="resource-picker-dropdown" role="listbox" aria-label="File options">
          {isLoading && (
            <div className="resource-picker-loading">
              <LoadingSpinner size="small" message="Loading files..." />
            </div>
          )}
          {error && (
            <div className="resource-picker-error">
              <ErrorDisplay
                error={error}
                title="Failed to load files"
                onRetry={() => refetch()}
              />
            </div>
          )}
          {!isLoading && !error && results.length === 0 && (
            <div className="resource-picker-empty">
              <p>No files found.</p>
              <Link to="/files" className="resource-picker-browse-link">
                Browse files
              </Link>
            </div>
          )}
          {!isLoading && !error && results.length > 0 && (
            <ul className="resource-picker-list" ref={listRef}>
              {results.map((file: FileItem, index: number) => (
                <li
                  key={file.id}
                  id={`file-picker-option-${file.id}`}
                  role="option"
                  aria-selected={value === file.id}
                  className={`resource-picker-option ${value === file.id ? 'selected' : ''} ${index === highlightedIndex ? 'highlighted' : ''}`}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    handleSelect(file);
                  }}
                  onMouseEnter={() => setHighlightedIndex(index)}
                >
                  <span className="resource-picker-option-name">{file.name}</span>
                  <span className="resource-picker-option-meta">{file.content_type}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <p className="resource-picker-hint">
        <Link to="/files" className="resource-picker-browse-link" data-testid="browse-files-link">
          Browse files
        </Link>
        {' '}to find and select a file.
      </p>
    </div>
  );
}
