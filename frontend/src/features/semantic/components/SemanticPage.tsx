/**
 * Semantic Page
 * Tabs: SPARQL Query, URI Lookup, Ontology Browser (real API; no mocks)
 */

import { useState } from 'react';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { SPARQLOutputFormat } from '../../../shared/types/semantic';
import {
  useJSONLDContext,
  useOntology,
  useResolveFieldURI,
  useResolveURI,
  useSPARQLQuery,
} from '../hooks/useSemantic';
import './SemanticPage.css';

type TabId = 'sparql' | 'uri-lookup' | 'ontology';

const TABS: { id: TabId; label: string }[] = [
  { id: 'sparql', label: 'SPARQL Query' },
  { id: 'uri-lookup', label: 'URI Lookup' },
  { id: 'ontology', label: 'Ontology' },
];

export function SemanticPage() {
  const [activeTab, setActiveTab] = useState<TabId>('sparql');
  const [sparqlQuery, setSparqlQuery] = useState('SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10');
  const [sparqlFormat, setSparqlFormat] = useState<SPARQLOutputFormat>('json');
  const [uriResourceType, setUriResourceType] = useState('asset');
  const [uriResourceId, setUriResourceId] = useState('');
  const [fieldAssetUuid, setFieldAssetUuid] = useState('');
  const [fieldName, setFieldName] = useState('');
  const [uriLookupType, setUriLookupType] = useState<'resource' | 'field'>('resource');

  const sparqlMutation = useSPARQLQuery();
  const uriQuery = useResolveURI(
    uriLookupType === 'resource' && uriResourceId ? uriResourceType : null,
    uriLookupType === 'resource' && uriResourceId ? uriResourceId : null
  );
  const fieldUriQuery = useResolveFieldURI(
    uriLookupType === 'field' && fieldAssetUuid && fieldName ? fieldAssetUuid : null,
    uriLookupType === 'field' && fieldAssetUuid && fieldName ? fieldName : null
  );
  const ontologyQuery = useOntology();
  const contextQuery = useJSONLDContext();

  const handleSPARQLSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await sparqlMutation.mutateAsync({
        query: sparqlQuery,
        format: sparqlFormat,
        timeout: 30,
      });
    } catch (err) {
      // Error handled by mutation
      console.error('SPARQL query failed:', err);
    }
  };

  const handleURILookup = () => {
    // Trigger query by changing state (handled by useQuery enabled flag)
    if (uriLookupType === 'resource' && uriResourceId) {
      uriQuery.refetch();
    } else if (uriLookupType === 'field' && fieldAssetUuid && fieldName) {
      fieldUriQuery.refetch();
    }
  };

  return (
    <div className="semantic-page" data-testid="semantic-page">
      <div className="semantic-page-header">
        <h1>Semantic</h1>
      </div>

      <div className="semantic-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`semantic-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="semantic-content">
        {activeTab === 'sparql' && (
          <section className="semantic-section" data-testid="semantic-sparql-section">
            <h2>SPARQL Query</h2>
            <form onSubmit={handleSPARQLSubmit} className="sparql-form">
              <div className="form-group">
                <label htmlFor="sparql-query">
                  SPARQL Query <span className="required">*</span>
                </label>
                <textarea
                  id="sparql-query"
                  value={sparqlQuery}
                  onChange={(e) => setSparqlQuery(e.target.value)}
                  rows={10}
                  required
                  placeholder="SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"
                  className="sparql-query-input"
                />
              </div>
              <div className="form-group">
                <label htmlFor="sparql-format">Output Format</label>
                <select
                  id="sparql-format"
                  value={sparqlFormat}
                  onChange={(e) => setSparqlFormat(e.target.value as SPARQLOutputFormat)}
                >
                  <option value="json">JSON</option>
                  <option value="csv">CSV</option>
                  <option value="turtle">Turtle</option>
                  <option value="xml">XML</option>
                </select>
              </div>
              <div className="form-actions">
                <button type="submit" className="btn-primary" disabled={sparqlMutation.isPending}>
                  {sparqlMutation.isPending ? 'Executing...' : 'Execute Query'}
                </button>
              </div>
            </form>

            {sparqlMutation.error && (
              <ErrorDisplay
                error={sparqlMutation.error}
                title="SPARQL query failed"
                onRetry={() => sparqlMutation.reset()}
              />
            )}

            {sparqlMutation.data && (
              <div className="sparql-results">
                <h3>Results</h3>
                {sparqlMutation.data.truncated && (
                  <div className="sparql-warning">
                    ⚠️ {sparqlMutation.data.warning || 'Results were truncated'}
                  </div>
                )}
                <pre className="sparql-results-json">
                  {JSON.stringify(sparqlMutation.data.results, null, 2)}
                </pre>
              </div>
            )}
          </section>
        )}

        {activeTab === 'uri-lookup' && (
          <section className="semantic-section" data-testid="semantic-uri-lookup-section">
            <h2>URI Lookup</h2>
            <div className="uri-lookup-form">
              <div className="form-group">
                <label htmlFor="uri-lookup-type">Lookup Type</label>
                <select
                  id="uri-lookup-type"
                  value={uriLookupType}
                  onChange={(e) => setUriLookupType(e.target.value as 'resource' | 'field')}
                >
                  <option value="resource">Resource URI</option>
                  <option value="field">Field URI</option>
                </select>
              </div>

              {uriLookupType === 'resource' ? (
                <>
                  <div className="form-group">
                    <label htmlFor="uri-resource-type">Resource Type</label>
                    <select
                      id="uri-resource-type"
                      value={uriResourceType}
                      onChange={(e) => setUriResourceType(e.target.value)}
                    >
                      <option value="asset">Asset</option>
                      <option value="contract">Contract</option>
                      <option value="dataset">Dataset</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label htmlFor="uri-resource-id">
                      Resource ID (UUID) <span className="required">*</span>
                    </label>
                    <input
                      id="uri-resource-id"
                      type="text"
                      value={uriResourceId}
                      onChange={(e) => setUriResourceId(e.target.value)}
                      placeholder="e.g., 123e4567-e89b-12d3-a456-426614174000"
                    />
                  </div>
                </>
              ) : (
                <>
                  <div className="form-group">
                    <label htmlFor="field-asset-uuid">
                      Asset UUID <span className="required">*</span>
                    </label>
                    <input
                      id="field-asset-uuid"
                      type="text"
                      value={fieldAssetUuid}
                      onChange={(e) => setFieldAssetUuid(e.target.value)}
                      placeholder="e.g., 123e4567-e89b-12d3-a456-426614174000"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="field-name">
                      Field Name <span className="required">*</span>
                    </label>
                    <input
                      id="field-name"
                      type="text"
                      value={fieldName}
                      onChange={(e) => setFieldName(e.target.value)}
                      placeholder="e.g., customer_id"
                    />
                  </div>
                </>
              )}

              <div className="form-actions">
                <button
                  type="button"
                  className="btn-primary"
                  onClick={handleURILookup}
                  disabled={
                    (uriLookupType === 'resource' && !uriResourceId) ||
                    (uriLookupType === 'field' && (!fieldAssetUuid || !fieldName)) ||
                    uriQuery.isLoading ||
                    fieldUriQuery.isLoading
                  }
                >
                  {uriQuery.isLoading || fieldUriQuery.isLoading ? 'Resolving...' : 'Resolve URI'}
                </button>
              </div>
            </div>

            {(uriQuery.error || fieldUriQuery.error) && (
              <ErrorDisplay
                error={uriQuery.error || fieldUriQuery.error || new Error('Unknown error')}
                title="URI resolution failed"
                onRetry={() => {
                  if (uriLookupType === 'resource') uriQuery.refetch();
                  else fieldUriQuery.refetch();
                }}
              />
            )}

            {(uriQuery.isLoading || fieldUriQuery.isLoading) && (
              <LoadingSpinner message="Resolving URI..." />
            )}

            {(uriQuery.data || fieldUriQuery.data) && (
              <div className="uri-results">
                <h3>JSON-LD Result</h3>
                <pre className="uri-results-json">
                  {JSON.stringify(uriQuery.data || fieldUriQuery.data, null, 2)}
                </pre>
              </div>
            )}
          </section>
        )}

        {activeTab === 'ontology' && (
          <section className="semantic-section" data-testid="semantic-ontology-section">
            <h2>Ontology</h2>
            {ontologyQuery.isLoading && <LoadingSpinner message="Loading ontology..." />}
            {ontologyQuery.error && (
              <ErrorDisplay
                error={ontologyQuery.error}
                title="Failed to load ontology"
                onRetry={() => ontologyQuery.refetch()}
              />
            )}
            {ontologyQuery.data && (
              <div className="ontology-content">
                <h3>Ontology Definition (Turtle)</h3>
                <pre className="ontology-turtle">{ontologyQuery.data}</pre>
              </div>
            )}

            <div className="semantic-divider" />

            <h2>JSON-LD Context</h2>
            {contextQuery.isLoading && <LoadingSpinner message="Loading JSON-LD context..." />}
            {contextQuery.error && (
              <ErrorDisplay
                error={contextQuery.error}
                title="Failed to load JSON-LD context"
                onRetry={() => contextQuery.refetch()}
              />
            )}
            {contextQuery.data && (
              <div className="context-content">
                <h3>JSON-LD Context</h3>
                <pre className="context-json">{JSON.stringify(contextQuery.data, null, 2)}</pre>
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
