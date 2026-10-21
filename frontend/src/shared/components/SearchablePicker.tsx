/**
 * Phase 278.G.4 — shared SearchablePicker for resource selectors.
 *
 * Search-as-you-type with debounce.  Single reusable component for
 * asset/contract/dataset/tenant/user/role pickers.
 */
import { useCallback, useEffect, useMemo, useState, type FC } from 'react';

export interface PickerOption {
  id: string;
  label: string;
  subtitle?: string;
}

export interface SearchablePickerProps {
  /** All available options. */
  options: PickerOption[];
  /** Currently selected option id (controlled). */
  value: string | null;
  /** Called when selection changes. */
  onChange: (id: string | null) => void;
  /** Placeholder text for the search input. */
  placeholder?: string;
  /** Label above the picker. */
  label?: string;
  /** Show a loading spinner while options load. */
  loading?: boolean;
  /** Error message to display below. */
  error?: string;
  /** Debounce delay for search filter (ms). */
  searchDelay?: number;
  'data-testid'?: string;
}

export const SearchablePicker: FC<SearchablePickerProps> = ({
  options,
  value,
  onChange,
  placeholder = 'Search...',
  label,
  loading = false,
  error,
  searchDelay = 200,
  'data-testid': testId = 'searchable-picker',
}) => {
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), searchDelay);
    return () => clearTimeout(timer);
  }, [query, searchDelay]);

  const filtered = useMemo(() => {
    if (!debouncedQuery) return options.slice(0, 20);
    const q = debouncedQuery.toLowerCase();
    return options
      .filter(
        (o) =>
          o.label.toLowerCase().includes(q) ||
          (o.subtitle && o.subtitle.toLowerCase().includes(q)),
      )
      .slice(0, 20);
  }, [options, debouncedQuery]);

  const selected = options.find((o) => o.id === value);

  const handleSelect = useCallback(
    (id: string) => {
      onChange(id);
      setQuery('');
      setOpen(false);
    },
    [onChange],
  );

  return (
    <div className="searchable-picker" data-testid={testId}>
      {label && <label className="searchable-picker__label">{label}</label>}
      <div className="searchable-picker__input-wrap">
        {selected && !open ? (
          <div
            className="searchable-picker__chip"
            onClick={() => setOpen(true)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && setOpen(true)}
          >
            <span>{selected.label}</span>
            {selected.subtitle && (
              <span className="searchable-picker__chip-sub">{selected.subtitle}</span>
            )}
            <button
              type="button"
              className="searchable-picker__clear-btn"
              onClick={(e) => {
                e.stopPropagation();
                onChange(null);
              }}
              aria-label="Clear selection"
            >
              &times;
            </button>
          </div>
        ) : (
          <input
            type="text"
            className="searchable-picker__input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 150)}
            placeholder={placeholder}
            autoComplete="off"
            aria-label={label || placeholder}
          />
        )}
        {loading && <span className="searchable-picker__spinner" />}
      </div>
      {open && (
        <ul className="searchable-picker__dropdown" role="listbox">
          {filtered.length === 0 && (
            <li className="searchable-picker__empty">No results</li>
          )}
          {filtered.map((opt) => (
            <li
              key={opt.id}
              className={`searchable-picker__option${opt.id === value ? ' searchable-picker__option--selected' : ''}`}
              role="option"
              aria-selected={opt.id === value}
              onMouseDown={() => handleSelect(opt.id)}
            >
              <span>{opt.label}</span>
              {opt.subtitle && (
                <span className="searchable-picker__option-sub">{opt.subtitle}</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {error && <span className="searchable-picker__error">{error}</span>}
    </div>
  );
};
