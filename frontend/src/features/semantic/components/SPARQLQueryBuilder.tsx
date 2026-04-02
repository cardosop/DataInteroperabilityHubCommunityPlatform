/**
 * SPARQLQueryBuilder — Phase 31 (29.3)
 *
 * Controlled SPARQL editor with format selector, result table/triple view,
 * error handling for invalid SPARQL, timeout, and rate limiting.
 */

import { useState } from 'react';
import { FeatureErrorBoundary } from '../../../shared/components/FeatureErrorBoundary';
import { useSPARQLQuery } from '../hooks/useSemantic';
import type { SPARQLOutputFormat, SPARQLQueryResponse } from '../../../shared/types/semantic';

const DEFAULT_QUERY = 'SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10';

function SPARQLQueryBuilderInner() {
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [format, setFormat] = useState<SPARQLOutputFormat>('json');
  const sparqlMutation = useSPARQLQuery();
  const [result, setResult] = useState<SPARQLQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setError(null);
    setResult(null);
    try {
      const res = await sparqlMutation.mutateAsync({ query, format });
      setResult(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('429')) setError('Rate limit exceeded. Please wait before retrying.');
      else if (msg.includes('408') || msg.includes('timeout')) setError('Query timed out.');
      else if (msg.includes('400')) setError('Invalid SPARQL query syntax.');
      else setError(msg);
    }
  };

  return (
    <div className="sparql-query-builder">
      <h2>SPARQL Query</h2>
      <textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        rows={8}
        style={{ width: '100%', fontFamily: 'monospace', fontSize: '0.875rem' }}
        placeholder="Enter SPARQL query..."
      />
      <div style={{ display: 'flex', gap: '0.5rem', margin: '0.5rem 0' }}>
        <select value={format} onChange={(e) => setFormat(e.target.value as SPARQLOutputFormat)}>
          <option value="json">JSON</option>
          <option value="turtle">Turtle</option>
          <option value="csv">CSV</option>
          <option value="xml">XML</option>
        </select>
        <button onClick={handleSubmit} disabled={sparqlMutation.isPending} type="button">
          {sparqlMutation.isPending ? 'Executing...' : 'Execute'}
        </button>
      </div>
      {error && <div style={{ color: 'var(--color-error, red)', margin: '0.5rem 0' }}>{error}</div>}
      {result && (
        <div style={{ marginTop: '1rem' }}>
          {result.truncated && (
            <div style={{ color: 'var(--color-warning, orange)', marginBottom: '0.5rem' }}>
              Results truncated. {result.warning}
            </div>
          )}
          <pre style={{ maxHeight: '400px', overflow: 'auto', fontSize: '0.8rem', background: 'var(--color-background-secondary, #f5f5f5)', padding: '1rem', borderRadius: '4px' }}>
            {typeof result.results === 'string' ? result.results : JSON.stringify(result.results, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export function SPARQLQueryBuilder() {
  return (
    <FeatureErrorBoundary feature="sparql-query-builder">
      <SPARQLQueryBuilderInner />
    </FeatureErrorBoundary>
  );
}
