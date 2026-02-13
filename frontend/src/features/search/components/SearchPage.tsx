/**
 * Full-Text Search Page
 * Input, filters, results list with links to /assets/:id, /contracts/:id, /datasets/:id
 */

import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { SearchResponse, SearchResultType } from '../../../shared/types/search';
import { searchService } from '../services/searchService';
import './SearchPage.css';

const RESULT_TYPE_OPTIONS: { value: '' | SearchResultType; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'ASSET', label: 'Assets' },
  { value: 'CONTRACT', label: 'Contracts' },
  { value: 'DATASET', label: 'Datasets' },
];

function resultHref(item: { type: string; id: string }): string {
  const base = item.type.toLowerCase() + 's';
  return `/${base}/${item.id}`;
}

export function SearchPage() {
  const [query, setQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<'' | SearchResultType>('');
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const runSearch = useCallback(async () => {
    setError(null);
    setSubmitted(true);
    setLoading(true);
    try {
      const filters = typeFilter
        ? { type: typeFilter as SearchResultType, limit: 50 }
        : { limit: 50 };
      const response = await searchService.search(query.trim(), filters);
      setData(response);
    } catch (err) {
      setError(normalizeError(err));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [query, typeFilter]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runSearch();
  };

  const showEmpty = submitted && !loading && !error && (!data || data.results.length === 0);
  const showResults = submitted && !loading && !error && data && data.results.length > 0;

  return (
    <div className="search-page" data-testid="search-page">
      <div className="search-page-header">
        <h1>Search</h1>
        <p className="search-page-subtitle">
          Full-text search across assets, contracts, and datasets
        </p>
      </div>

      <form className="search-page-input-section" onSubmit={handleSubmit}>
        <div className="search-page-input-row">
          <input
            type="search"
            placeholder="Enter search query..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search query"
            className="search-page-query-input"
          />
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
        <div className="search-page-filters">
          <label htmlFor="search-type-filter">Type</label>
          <select
            id="search-type-filter"
            value={typeFilter}
            onChange={(e) => setTypeFilter((e.target.value || '') as '' | SearchResultType)}
            aria-label="Filter by type"
          >
            {RESULT_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value || 'all'} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </form>

      {loading && <LoadingSpinner message="Searching..." />}

      {error && <ErrorDisplay error={error} title="Search failed" onRetry={runSearch} />}

      {showEmpty && (
        <EmptyState
          title="No results"
          message={
            query.trim()
              ? `No results found for "${query.trim()}". Try different keywords or filters.`
              : 'Enter a search query above to find assets, contracts, and datasets.'
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
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!submitted && !loading && !error && (
        <EmptyState
          title="Start searching"
          message="Enter a query above and click Search to find assets, contracts, and datasets."
          icon="🔍"
        />
      )}
    </div>
  );
}
