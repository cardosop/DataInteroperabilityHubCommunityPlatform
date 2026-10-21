/**
 * AI Natural Language Search Page
 * Provides natural language search interface
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useNaturalLanguageSearch } from '../hooks/useAI';
import type { NaturalLanguageSearchResponse } from '../../../shared/types/ai';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import './AISearchPage.css';
import { Button } from '../../../shared/components/Button';

interface SearchResultItem {
  id: string;
  name?: string;
  key?: string;
  description?: string;
}

export function AISearchPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [resultTypes, setResultTypes] = useState<('assets' | 'contracts' | 'datasets')[]>(['assets', 'contracts', 'datasets']);
  const [searchResults, setSearchResults] = useState<NaturalLanguageSearchResponse | null>(null);
  const searchMutation = useNaturalLanguageSearch();

  const handleSearch = async () => {
    if (!query.trim()) return;

    try {
      const results = await searchMutation.mutateAsync({
        query: query.trim(),
        result_types: resultTypes,
      });
      setSearchResults(results);
    } catch {
      // Error handled by mutation
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  const handleResultClick = (type: string, id: string) => {
    if (type === 'assets') navigate(`/assets/${id}`);
    else if (type === 'contracts') navigate(`/contracts/${id}`);
    else if (type === 'datasets') navigate(`/datasets/${id}`);
  };

  return (
    <div className="ai-search-page">
      <div className="ai-search-header">
        <h1>AI Natural Language Search</h1>
        <p className="subtitle">Ask questions in natural language to find assets, contracts, and datasets</p>
      </div>

      <div className="ai-search-input-section">
        <div className="search-input-container">
          <textarea
            className="search-input"
            placeholder="e.g., 'Show me all customer data assets from last month' or 'Find contracts related to GDPR compliance'"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={handleKeyPress}
            rows={3}
          />
          <Button
 variant="primary" className="search-button"
 onClick={handleSearch}
 disabled={!query.trim() || searchMutation.isPending}>
            {searchMutation.isPending ? 'Searching...' : 'Search'}
          </Button>
        </div>

        <div className="result-types-selector">
          <label>Search in:</label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={resultTypes.includes('assets')}
              onChange={(e) => {
                if (e.target.checked) {
                  setResultTypes([...resultTypes, 'assets']);
                } else {
                  setResultTypes(resultTypes.filter(t => t !== 'assets'));
                }
              }}
            />
            Assets
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={resultTypes.includes('contracts')}
              onChange={(e) => {
                if (e.target.checked) {
                  setResultTypes([...resultTypes, 'contracts']);
                } else {
                  setResultTypes(resultTypes.filter(t => t !== 'contracts'));
                }
              }}
            />
            Contracts
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={resultTypes.includes('datasets')}
              onChange={(e) => {
                if (e.target.checked) {
                  setResultTypes([...resultTypes, 'datasets']);
                } else {
                  setResultTypes(resultTypes.filter(t => t !== 'datasets'));
                }
              }}
            />
            Datasets
          </label>
        </div>
      </div>

      {searchMutation.isPending && (
        <LoadingSpinner message="Understanding your query and searching..." />
      )}

      {!!searchMutation.error && (
        <ErrorDisplay
          error={searchMutation.error}
          title="Search failed"
          onRetry={handleSearch}
        />
      )}

      {searchResults && !searchMutation.isPending && (
        <div className="search-results">
          <div className="search-meta">
            <div className="interpreted-query">
              <h3>Query Understanding</h3>
              <p><strong>Intent:</strong> {searchResults.interpreted_query.intent}</p>
              {searchResults.interpreted_query.entities.length > 0 && (
                <p><strong>Entities:</strong> {searchResults.interpreted_query.entities.join(', ')}</p>
              )}
              {searchResults.interpreted_query.time_range && (
                <p><strong>Time Range:</strong> {searchResults.interpreted_query.time_range}</p>
              )}
            </div>
            <div className="search-stats">
              <p>Execution time: {searchResults.execution_time_ms}ms</p>
              {searchResults.cached && <span className="cached-badge">Cached</span>}
            </div>
          </div>

          <div className="results-container">
            {searchResults.results.assets && searchResults.results.assets.total > 0 && (
              <div className="result-section">
                <h3>Assets ({searchResults.results.assets.total})</h3>
                <div className="results-list">
                  {(searchResults.results.assets.items as SearchResultItem[]).map((item) => (
                    <div
                      key={item.id}
                      className="result-item"
                      onClick={() => handleResultClick('assets', item.id)}
                    >
                      <h4>{item.name || item.key}</h4>
                      {item.description && <p>{item.description}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {searchResults.results.contracts && searchResults.results.contracts.total > 0 && (
              <div className="result-section">
                <h3>Contracts ({searchResults.results.contracts.total})</h3>
                <div className="results-list">
                  {(searchResults.results.contracts.items as SearchResultItem[]).map((item) => (
                    <div
                      key={item.id}
                      className="result-item"
                      onClick={() => handleResultClick('contracts', item.id)}
                    >
                      <h4>{item.name || item.id}</h4>
                      {item.description && <p>{item.description}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {searchResults.results.datasets && searchResults.results.datasets.total > 0 && (
              <div className="result-section">
                <h3>Datasets ({searchResults.results.datasets.total})</h3>
                <div className="results-list">
                  {(searchResults.results.datasets.items as SearchResultItem[]).map((item) => (
                    <div
                      key={item.id}
                      className="result-item"
                      onClick={() => handleResultClick('datasets', item.id)}
                    >
                      <h4>{item.name || item.id}</h4>
                      {item.description && <p>{item.description}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(!searchResults.results.assets || searchResults.results.assets.total === 0) &&
              (!searchResults.results.contracts || searchResults.results.contracts.total === 0) &&
              (!searchResults.results.datasets || searchResults.results.datasets.total === 0) && (
                <EmptyState
                  title="No results found"
                  message="Try rephrasing your query or adjusting the search filters."
                />
              )}
          </div>
        </div>
      )}

      {!searchResults && !searchMutation.isPending && !searchMutation.error && (
        <EmptyState
          title="Start searching"
          message="Enter a natural language query above to search across assets, contracts, and datasets."
        />
      )}
    </div>
  );
}
