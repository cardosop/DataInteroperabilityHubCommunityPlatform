/**
 * Semantic Page
 * Tabs: SPARQL Query, URI Lookup, Ontology Browser (real API; no mocks)
 */

import { useState } from 'react';
import ReactCodeMirror from '@uiw/react-codemirror';
import { StreamLanguage } from '@codemirror/language';
import { sparql } from '@codemirror/legacy-modes/mode/sparql';
import { Banner } from '../../../shared/components/Banner';
import { Button } from '../../../shared/components/Button';
import { CodeBlock } from '../../../shared/components/CodeBlock';
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
import { useSPARQLHistory } from '../hooks/useSPARQLHistory';
import { OntologyTree } from './OntologyTree';
import { SPARQLResultTable } from './SPARQLResultTable';
import './SemanticPage.css';

type TabId = 'sparql' | 'uri-lookup' | 'ontology' | 'export';
type OntologySubTab = 'turtle' | 'jsonld';
type ExportFormat = 'n-triples' | 'turtle' | 'rdf-xml' | 'ld+json';

const TABS: { id: TabId; label: string }[] = [
  { id: 'sparql', label: 'SPARQL Query' },
  { id: 'uri-lookup', label: 'URI Lookup' },
  { id: 'ontology', label: 'Ontology' },
  { id: 'export', label: 'Export' },
];

const EXPORT_FORMATS: { value: ExportFormat; label: string; ext: string }[] = [
  { value: 'n-triples', label: 'N-Triples', ext: 'nt' },
  { value: 'turtle', label: 'Turtle', ext: 'ttl' },
  { value: 'rdf-xml', label: 'RDF/XML', ext: 'rdf' },
  { value: 'ld+json', label: 'JSON-LD', ext: 'jsonld' },
];

const sparqlLang = StreamLanguage.define(sparql);

export function SemanticPage() {
  const [activeTab, setActiveTab] = useState<TabId>('sparql');
  const [sparqlQuery, setSparqlQuery] = useState('SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10');
  const [sparqlFormat, setSparqlFormat] = useState<SPARQLOutputFormat>('json');
  const [uriResourceType, setUriResourceType] = useState('asset');
  const [uriResourceId, setUriResourceId] = useState('');
  const [fieldAssetUuid, setFieldAssetUuid] = useState('');
  const [fieldName, setFieldName] = useState('');
  const [uriLookupType, setUriLookupType] = useState<'resource' | 'field'>('resource');
  const [ontologySubTab, setOntologySubTab] = useState<OntologySubTab>('turtle');
  // Phase 230.2.10 — Export tab state.
  const [exportFormat, setExportFormat] = useState<ExportFormat>('n-triples');
  const [exportLoading, setExportLoading] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportSize, setExportSize] = useState<number | null>(null);

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
  const { history, pushToHistory, clearHistory } = useSPARQLHistory();

  const handleSPARQLSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await sparqlMutation.mutateAsync({
        query: sparqlQuery,
        format: sparqlFormat,
        timeout: 30,
      });
      pushToHistory(sparqlQuery);
    } catch (err) {
      // Error handled by mutation
      console.error('SPARQL query failed:', err);
    }
  };

  const handleExport = async () => {
    setExportLoading(true);
    setExportError(null);
    setExportSize(null);
    try {
      const { semanticService } = await import('../services/semanticService');
      const blob = await semanticService.exportRdf(exportFormat);
      setExportSize(blob.size);
      // Trigger browser download via an in-memory <a download> click.
      const fmt = EXPORT_FORMATS.find((f) => f.value === exportFormat);
      const ext = fmt ? fmt.ext : 'rdf';
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `semantic-export.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      // Surface a structured error message — 413 (cap exceeded) and
      // 429 (throttle) include guidance the user can act on.
      const message = err instanceof Error ? err.message : 'Export failed';
      setExportError(message);
    } finally {
      setExportLoading(false);
    }
  };

  const handleURILookup = () => {
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
                <ReactCodeMirror
                  value={sparqlQuery}
                  onChange={(value) => setSparqlQuery(value)}
                  extensions={[sparqlLang]}
                  basicSetup={{ lineNumbers: true, foldGutter: false }}
                  minHeight="150px"
                  maxHeight="400px"
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
                <Button type="submit" variant="primary" loading={sparqlMutation.isPending}>
                  Execute Query
                </Button>
              </div>
            </form>

            {/* SPARQL History */}
            {history.length > 0 && (
              <details className="sparql-history">
                <summary>History ({history.length})</summary>
                <ul className="sparql-history__list">
                  {history.map((entry, idx) => (
                    <li key={idx}>
                      <button
                        type="button"
                        className="sparql-history__entry"
                        onClick={() => setSparqlQuery(entry)}
                        title={entry}
                      >
                        {entry.length > 80 ? entry.slice(0, 80) + '...' : entry}
                      </button>
                    </li>
                  ))}
                </ul>
                <Button variant="ghost" size="sm" onClick={clearHistory}>
                  Clear history
                </Button>
              </details>
            )}

            {!!sparqlMutation.error && (
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
                  <Banner variant="warning">
                    {sparqlMutation.data.warning || 'Results were truncated'}
                  </Banner>
                )}
                {(() => {
                  const results = sparqlMutation.data?.results as Record<string, unknown> | string | undefined;
                  const bindings = typeof results === 'object' && results !== null
                    ? (results as Record<string, unknown>).bindings
                    : undefined;
                  if (sparqlFormat === 'json' && Array.isArray(bindings)) {
                    const head = (results as Record<string, unknown>).head as { vars?: string[] } | undefined;
                    const vars = head?.vars ?? ((results as Record<string, unknown>).vars as string[] | undefined) ?? [];
                    return <SPARQLResultTable vars={vars} bindings={bindings} />;
                  }
                  return (
                    <CodeBlock
                      language={sparqlFormat === 'csv' ? 'plaintext' : sparqlFormat}
                      code={typeof results === 'string'
                        ? results
                        : JSON.stringify(results, null, 2)}
                    />
                  );
                })()}
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
                <Button
                  variant="primary"
                  onClick={handleURILookup}
                  disabled={
                    (uriLookupType === 'resource' && !uriResourceId) ||
                    (uriLookupType === 'field' && (!fieldAssetUuid || !fieldName)) ||
                    uriQuery.isLoading ||
                    fieldUriQuery.isLoading
                  }
                >
                  {uriQuery.isLoading || fieldUriQuery.isLoading ? 'Resolving...' : 'Resolve URI'}
                </Button>
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
                <CodeBlock
                  language="json"
                  code={JSON.stringify(uriQuery.data || fieldUriQuery.data, null, 2)}
                />
              </div>
            )}
          </section>
        )}

        {activeTab === 'ontology' && (
          <section className="semantic-section" data-testid="semantic-ontology-section">
            <h2>Ontology</h2>

            {/* Sub-tab bar */}
            <div className="semantic-subtabs">
              <button
                type="button"
                className={`semantic-subtab ${ontologySubTab === 'turtle' ? 'active' : ''}`}
                onClick={() => setOntologySubTab('turtle')}
              >
                Turtle
              </button>
              <button
                type="button"
                className={`semantic-subtab ${ontologySubTab === 'jsonld' ? 'active' : ''}`}
                onClick={() => setOntologySubTab('jsonld')}
              >
                JSON-LD Context
              </button>
            </div>

            {ontologySubTab === 'turtle' && (
              <>
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
                    <OntologyTree turtle={ontologyQuery.data} />
                    <CodeBlock language="turtle" code={ontologyQuery.data} />
                  </div>
                )}
              </>
            )}

            {ontologySubTab === 'jsonld' && (
              <>
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
                    <CodeBlock
                      language="json"
                      code={JSON.stringify(contextQuery.data, null, 2)}
                    />
                  </div>
                )}
              </>
            )}
          </section>
        )}

        {activeTab === 'export' && (
          <section
            className="semantic-section"
            data-testid="semantic-export-section"
          >
            <h2>Bulk RDF Export</h2>
            <p className="semantic-export-help">
              Export your tenant&rsquo;s entire semantic graph in the
              requested RDF serialization. Throttled to 5 requests / 5
              minutes / user. Hard cap 100 million triples — above this,
              use <code>SPARQL pagination</code> via the SPARQL Query tab.
            </p>
            <div className="form-group">
              <label htmlFor="export-format">Format</label>
              <select
                id="export-format"
                data-testid="semantic-export-format"
                value={exportFormat}
                onChange={(e) => setExportFormat(e.target.value as ExportFormat)}
                disabled={exportLoading}
              >
                {EXPORT_FORMATS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              data-testid="semantic-export-download"
              onClick={handleExport}
              disabled={exportLoading}
              aria-busy={exportLoading ? 'true' : 'false'}
            >
              {exportLoading ? 'Exporting…' : 'Download'}
            </button>
            {exportError && (
              <p
                role="alert"
                data-testid="semantic-export-error"
                className="semantic-export-error"
              >
                {exportError}
              </p>
            )}
            {exportSize != null && (
              <p
                data-testid="semantic-export-size"
                className="semantic-export-size"
                role="status"
                aria-live="polite"
              >
                Last export: {(exportSize / 1024).toFixed(1)} KB
              </p>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
