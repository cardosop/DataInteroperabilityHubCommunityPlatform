/**
 * Full-Text Search Page (223.6).
 *
 * Changes vs. the pre-223.6 page:
 *   - Scope tabs (All / Assets / Contracts / Datasets / Jobs / Orders)
 *     replace the old `<select>`. Jobs and Orders are not yet indexed
 *     server-side — clicking them renders an informational empty-state
 *     (no spurious backend call) so the UX promises nothing the backend
 *     can't deliver today.
 *   - Recent searches dropdown shown when the query input is focused
 *     and empty. Clicking an entry fills the input AND triggers a
 *     search via the debounce path.
 *   - Auto-search: typing or changing a filter debounces 300ms and
 *     runs the query. The "Search" button is gone — Enter in the input
 *     just blurs focus; the debounce handles submission. Queries are
 *     persisted to the recent-searches store on successful fetch.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useDebouncedValue } from '../../../shared/hooks/useDebouncedValue';
import type { ApiError } from '../../../shared/types/api';
import type { SearchResponse, SearchResultType } from '../../../shared/types/search';
import { normalizeError } from '../../../shared/utils/errorUtils';
import {
  getRecentSearches,
  recordSearch,
  type RecentSearchEntry,
} from '../../../shared/utils/recentSearches';
import { searchService } from '../services/searchService';
import { useMeshDomains } from '../../mesh/hooks/useMesh';
import './SearchPage.css';

type ScopeValue = 'ALL' | SearchResultType | 'JOB' | 'ORDER';

interface Scope {
  value: ScopeValue;
  label: string;
  /**
   * `true` for scopes the backend full-text index supports today. Others
   * render an informational empty-state without issuing a request.
   */
  supported: boolean;
}

// Phase 273.6 — Jobs/Orders removed per D273.11 (UI tabs follow backend index, never lead).
const SCOPES: Scope[] = [
  { value: 'ALL', label: 'All', supported: true },
  { value: 'ASSET', label: 'Assets', supported: true },
  { value: 'CONTRACT', label: 'Contracts', supported: true },
  { value: 'DATASET', label: 'Datasets', supported: true },
];

const SEARCH_DEBOUNCE_MS = 300;

function resultHref(item: { type: string; id: string }): string {
  const base = item.type.toLowerCase() + 's';
  return `/${base}/${item.id}`;
}

function toSearchResultType(scope: ScopeValue): '' | SearchResultType {
  if (scope === 'ALL' || scope === 'JOB' || scope === 'ORDER') return '';
  return scope;
}

export function SearchPage() {
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get('q') || '');
  const [scope, setScope] = useState<ScopeValue>('ALL');
  const [domainFilter, setDomainFilter] = useState('');
  const [dqStatusFilter, setDqStatusFilter] = useState('');
  const [complianceFilter, setComplianceFilter] = useState('');

  // Populate domain dropdown from mesh domains API (graceful degradation:
  // if mesh backend is unavailable, the dropdown shows only "All domains")
  const { data: domainsData } = useMeshDomains();

  // Phase 230.11 (REQ-SEM-SEARCH-EXPAND-001) — ontology-aware search
  // toggle.  Off by default — preserves existing search semantics
  // unless the user explicitly opts in.
  const [semanticEnabled, setSemanticEnabled] = useState(false);

  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const [showRecents, setShowRecents] = useState(false);
  const [recentSearches, setRecentSearches] = useState<RecentSearchEntry[]>(() =>
    getRecentSearches(),
  );

  // Debounced triggers. We debounce both the query *and* the filter values
  // so clicking through scopes quickly doesn't fire a storm of requests.
  const debouncedQuery = useDebouncedValue(query, SEARCH_DEBOUNCE_MS);
  const debouncedScope = useDebouncedValue(scope, SEARCH_DEBOUNCE_MS);
  const debouncedDomain = useDebouncedValue(domainFilter, SEARCH_DEBOUNCE_MS);
  const debouncedDq = useDebouncedValue(dqStatusFilter, SEARCH_DEBOUNCE_MS);
  const debouncedCompliance = useDebouncedValue(complianceFilter, SEARCH_DEBOUNCE_MS);
  const debouncedSemantic = useDebouncedValue(semanticEnabled, SEARCH_DEBOUNCE_MS);

  const currentScopeSupported = SCOPES.find((s) => s.value === debouncedScope)?.supported ?? true;

  // Effect-driven search — runs whenever any debounced input changes.
  // Guards: empty query → don't fire; unsupported scope → don't fire and
  // clear the last result so the empty-state is honest.
  useEffect(() => {
    const q = debouncedQuery.trim();
    if (!q) {
      setData(null);
      setSubmitted(false);
      setLoading(false);
      return;
    }
    if (!currentScopeSupported) {
      setData(null);
      setSubmitted(true);
      setLoading(false);
      return;
    }

    let cancelled = false;
    const filters: Record<string, string | number | boolean> = { limit: 50 };
    const type = toSearchResultType(debouncedScope);
    if (type) filters.type = type;
    if (debouncedDomain) filters.domain = debouncedDomain;
    if (debouncedDq) filters.quality_status = debouncedDq;
    if (debouncedCompliance) filters.compliance_status = debouncedCompliance;
    if (debouncedSemantic) filters.semantic = true;

    setLoading(true);
    setError(null);
    setSubmitted(true);
    searchService
      .search(q, filters)
      .then((response) => {
        if (cancelled) return;
        setData(response);
        recordSearch(q);
        setRecentSearches(getRecentSearches());
      })
      .catch((err) => {
        if (cancelled) return;
        setError(normalizeError(err));
        setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [
    debouncedQuery,
    debouncedScope,
    debouncedDomain,
    debouncedDq,
    debouncedCompliance,
    debouncedSemantic,
    currentScopeSupported,
  ]);

  const wrapperRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!showRecents) return;
    const onDocClick = (e: MouseEvent) => {
      if (!wrapperRef.current?.contains(e.target as Node)) setShowRecents(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [showRecents]);

  const handleRecentClick = useCallback((entry: RecentSearchEntry) => {
    setQuery(entry.query);
    setShowRecents(false);
  }, []);

  const showEmpty =
    submitted && !loading && !error && (!data || data.results.length === 0);
  const showResults =
    submitted && !loading && !error && data && data.results.length > 0;

  return (
    <div className="search-page" data-testid="search-page">
      <div className="search-page-header">
        <h1>Search</h1>
        <p className="search-page-subtitle">
          Full-text search across assets, contracts, and datasets
        </p>
      </div>

      <div className="search-page-input-section">
        <div className="search-page-input-row" ref={wrapperRef}>
          <input
            type="search"
            placeholder="Enter search query..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setShowRecents(true)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') setShowRecents(false);
            }}
            aria-label="Search query"
            className="search-page-query-input"
            data-testid="search-input"
          />
          {showRecents && query.trim() === '' && recentSearches.length > 0 && (
            <ul
              className="search-page-recent-dropdown"
              role="listbox"
              aria-label="Recent searches"
              data-testid="search-recent-dropdown"
            >
              {recentSearches.map((entry) => (
                <li key={`${entry.query}-${entry.timestamp}`}>
                  <button
                    type="button"
                    role="option"
                    aria-selected="false"
                    className="search-page-recent-item"
                    onClick={() => handleRecentClick(entry)}
                    data-testid={`search-recent-${entry.query}`}
                  >
                    <span className="search-page-recent-query">{entry.query}</span>
                    <span className="search-page-recent-timestamp">
                      {new Date(entry.timestamp).toLocaleString()}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div
          className="search-page-scope-tabs"
          role="tablist"
          aria-label="Search scope"
          data-testid="search-scope-tabs"
        >
          {SCOPES.map((s) => (
            <button
              key={s.value}
              type="button"
              role="tab"
              aria-selected={scope === s.value}
              className={`search-page-scope-tab ${scope === s.value ? 'active' : ''}`}
              onClick={() => setScope(s.value)}
              data-testid={`search-scope-${s.value}`}
              title={s.supported ? undefined : 'Not yet indexed'}
            >
              {s.label}
              {!s.supported && (
                <span className="search-page-scope-hint"> (soon)</span>
              )}
            </button>
          ))}
        </div>

        <div className="search-page-filters">
          <div className="search-filter-group">
            <label htmlFor="search-domain-filter">Domain</label>
            <select
              id="search-domain-filter"
              value={domainFilter}
              onChange={(e) => setDomainFilter(e.target.value)}
              aria-label="Filter by domain"
              className="search-filter-select"
            >
              <option value="">All domains</option>
              {domainsData?.results?.map((d) => (
                <option key={d.id} value={d.name}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
          <div className="search-filter-group">
            <label htmlFor="search-dq-filter">DQ Status</label>
            <select
              id="search-dq-filter"
              value={dqStatusFilter}
              onChange={(e) => setDqStatusFilter(e.target.value)}
              aria-label="Filter by DQ status"
            >
              <option value="">All</option>
              <option value="PASSED">Passed</option>
              <option value="FAILED">Failed</option>
              <option value="WARNING">Warning</option>
              <option value="PENDING">Pending</option>
            </select>
          </div>
          <div className="search-filter-group">
            <label htmlFor="search-compliance-filter">Compliance</label>
            <select
              id="search-compliance-filter"
              value={complianceFilter}
              onChange={(e) => setComplianceFilter(e.target.value)}
              aria-label="Filter by compliance status"
            >
              <option value="">All</option>
              <option value="COMPLIANT">Compliant</option>
              <option value="NON_COMPLIANT">Non-Compliant</option>
              <option value="WARNING">Warning</option>
              <option value="PENDING">Pending</option>
            </select>
          </div>
          <div className="search-filter-group search-filter-semantic">
            <label htmlFor="search-semantic-toggle" className="search-semantic-label">
              <input
                id="search-semantic-toggle"
                type="checkbox"
                checked={semanticEnabled}
                onChange={(e) => setSemanticEnabled(e.target.checked)}
                aria-label="Toggle ontology-aware search"
                data-testid="search-semantic-toggle"
              />
              <span>Ontology-aware search</span>
            </label>
            <span className="search-filter-hint">
              Expands queries via tenant ontology relations (synonyms,
              equivalent classes, parent/child concepts).
            </span>
          </div>
        </div>
      </div>

      {loading && <LoadingSpinner message="Searching..." />}

      {error && <ErrorDisplay error={error} title="Search failed" />}

      {!currentScopeSupported && submitted && !loading && !error && (
        <EmptyState
          title={`${SCOPES.find((s) => s.value === debouncedScope)?.label} search coming soon`}
          message={`Full-text indexing for ${SCOPES.find((s) => s.value === debouncedScope)?.label.toLowerCase()} is not yet live. Try a different scope.`}
          icon="🔧"
        />
      )}

      {currentScopeSupported && showEmpty && (
        <EmptyState
          title="No results"
          message={
            debouncedQuery.trim()
              ? `No results found for "${debouncedQuery.trim()}". Try different keywords or filters.`
              : 'Enter a search query above.'
          }
          icon="🔍"
        />
      )}

      {showResults && data && (
        <div className="search-page-results">
          <div className="search-page-results-meta">
            {data.total} result{data.total !== 1 ? 's' : ''} for &quot;{data.query}&quot;
          </div>
          <ul className="search-page-results-list" aria-label="Search results">
            {data.results.map((item) => (
              <li key={`${item.type}-${item.id}`} className="search-page-result-item">
                <Link to={resultHref(item)}>
                  <span className={`result-type-badge ${item.type}`}>{item.type}</span>
                  <h3>{item.title}</h3>
                  {item.description && <p>{item.description}</p>}
                  <span className="relevance-score">
                    Relevance: {(item.relevance_score * 100).toFixed(0)}%
                  </span>
                  {item.matched_via === 'ontology' && item.bridge_term && (
                    <span
                      className="ontology-match-badge"
                      data-testid={`ontology-badge-${item.id}`}
                      title="Surfaced via ontology-aware query expansion"
                    >
                      matched via ontology: {item.bridge_term}
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!submitted && !loading && !error && (
        <EmptyState
          title="Start searching"
          message="Start typing above to find assets, contracts, and datasets."
          icon="🔍"
        />
      )}
    </div>
  );
}
