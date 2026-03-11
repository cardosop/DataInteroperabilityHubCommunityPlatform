/**
 * ContractPicker Component
 * Searchable, single-select picker for choosing an existing contract.
 * Used in AssetDetailPage (attach contract), ODPSLinkPage, etc.
 * Supports keyboard navigation (ArrowDown, ArrowUp, Enter, Escape).
 * Optional spec_type filter for ODPS-only contracts.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useContracts, useContract } from '../../../features/contracts/hooks/useContracts';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { LoadingSpinner } from '../LoadingSpinner';
import { ErrorDisplay } from '../ErrorDisplay';
import { FEATURE_RESOURCE_PICKERS_ENABLED } from '../../config/featureFlags';
import type { Contract } from '../../types/contracts';
import './picker-base.css';

const SEARCH_DEBOUNCE_MS = 300;

export interface ContractPickerProps {
  value: string | null;
  onChange: (contractId: string | null) => void;
  placeholder?: string;
  disabled?: boolean;
  /** Filter by spec_type (e.g. ODPS for ODPS Link page) */
  specType?: string;
  'data-testid'?: string;
}

function getContractLabel(c: Contract): string {
  const name = c.name ?? (c.hub_contract_json?.info as { name?: string })?.name;
  return name || c.id.slice(0, 8) + '...';
}

export function ContractPicker({
  value,
  onChange,
  placeholder = 'Search and select a contract...',
  disabled = false,
  specType,
  'data-testid': dataTestId = 'contract-picker',
}: ContractPickerProps) {
  if (!FEATURE_RESOURCE_PICKERS_ENABLED) {
    return (
      <div className="contract-picker resource-picker" data-testid={dataTestId}>
        <input
          type="text"
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value.trim() || null)}
          placeholder="Enter contract ID (UUID)"
          disabled={disabled}
          className="resource-picker-input"
          aria-label="Contract ID"
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
    spec_type: specType,
  };

  const { data, isLoading, error, refetch } = useContracts(filters, { enabled: isOpen });

  const results = data?.results ?? [];
  const maxIndex = results.length - 1;

  const handleSelect = useCallback(
    (contract: Contract) => {
      onChange(contract.id);
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

  const selectedFromList = value ? results.find((c: Contract) => c.id === value) : null;
  const { data: selectedContractData } = useContract(value);
  const selectedContract =
    selectedFromList ?? (value && selectedContractData ? selectedContractData : null);

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
              : selectedContract
                ? `${getContractLabel(selectedContract)}${selectedContract.original_spec_type ? ` (${selectedContract.original_spec_type})` : ''}`
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
          aria-label="Select contract"
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-activedescendant={
            highlightedIndex >= 0 && results[highlightedIndex]
              ? `contract-picker-option-${results[highlightedIndex].id}`
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
        <div className="resource-picker-dropdown" role="listbox" aria-label="Contract options">
          {isLoading && (
            <div className="resource-picker-loading">
              <LoadingSpinner size="small" message="Loading contracts..." />
            </div>
          )}
          {error && (
            <div className="resource-picker-error">
              <ErrorDisplay
                error={error}
                title="Failed to load contracts"
                onRetry={() => refetch()}
              />
            </div>
          )}
          {!isLoading && !error && results.length === 0 && (
            <div className="resource-picker-empty">
              <p>No contracts found.</p>
              <Link to="/contracts" className="resource-picker-browse-link">
                Browse contracts
              </Link>
            </div>
          )}
          {!isLoading && !error && results.length > 0 && (
            <ul className="resource-picker-list" ref={listRef}>
              {results.map((contract: Contract, index: number) => (
                <li
                  key={contract.id}
                  id={`contract-picker-option-${contract.id}`}
                  role="option"
                  aria-selected={value === contract.id}
                  className={`resource-picker-option ${value === contract.id ? 'selected' : ''} ${index === highlightedIndex ? 'highlighted' : ''}`}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    handleSelect(contract);
                  }}
                  onMouseEnter={() => setHighlightedIndex(index)}
                >
                  <span className="resource-picker-option-name">{getContractLabel(contract)}</span>
                  <span className="resource-picker-option-meta">
                    {contract.original_spec_type || contract.id.slice(0, 8)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <p className="resource-picker-hint">
        <Link to="/contracts" className="resource-picker-browse-link" data-testid="browse-contracts-link">
          Browse contracts
        </Link>
        {' '}to find and select a contract.
      </p>
    </div>
  );
}
