/**
 * RelationshipsPanel
 *
 * Displays contract relationships from hub_contract_json, grouped by
 * source model.  Shows an empty state for contracts without relationships
 * (pre-v3.1.0 ODCS contracts).
 */

import { Link } from 'react-router-dom';
import type { ContractRelationship, ContractSchemaObject } from '../../../shared/types/contracts';
import { useContractRelationships } from '../../semantic/hooks/useSemantic';
import './RelationshipsPanel.css';

interface RelationshipsPanelProps {
  /** models[] from hub_contract_json */
  models?: ContractSchemaObject[];
  /** schema-level relationships from hub_contract_json.schema */
  schemaRelationships?: ContractRelationship[];
  /** original_spec_version for empty-state messaging */
  specVersion?: string;
  /**
   * Phase 230.5.6 — when supplied, the panel additionally fetches
   * RDF relationship triples from
   * ``GET /api/v1/semantic/relationships/{contractId}`` and renders
   * them below the structural relationships table.  When omitted,
   * the panel only shows the structural data (legacy behaviour).
   */
  contractId?: string;
}

/** Badge colour by relationship type */
function typeBadgeClass(type?: string): string {
  switch (type) {
    case 'foreignKey':
      return 'rel-badge rel-badge-fk';
    case 'oneToOne':
      return 'rel-badge rel-badge-1to1';
    case 'oneToMany':
      return 'rel-badge rel-badge-1toN';
    default:
      return 'rel-badge';
  }
}

function RelationshipRow({ rel }: { rel: ContractRelationship }) {
  const targetLabel = [rel.target_contract, rel.target_model]
    .filter(Boolean)
    .join(' / ');

  return (
    <tr className="rel-row">
      <td className="rel-cell rel-cell-source">
        <code>{rel.source?.join(', ') || '—'}</code>
      </td>
      <td className="rel-cell rel-cell-type">
        <span className={typeBadgeClass(rel.type)}>{rel.type || 'unknown'}</span>
      </td>
      <td className="rel-cell rel-cell-target">
        {rel.target_contract ? (
          <Link
            to={`/contracts/${rel.target_contract}`}
            className="rel-link"
            title={`Go to contract ${rel.target_contract}`}
          >
            {targetLabel}
          </Link>
        ) : (
          <span>{targetLabel || '—'}</span>
        )}
      </td>
      <td className="rel-cell rel-cell-target-props">
        <code>{rel.target_properties?.join(', ') || '—'}</code>
      </td>
      <td className="rel-cell rel-cell-desc">{rel.description || ''}</td>
    </tr>
  );
}

export function RelationshipsPanel({
  models,
  schemaRelationships,
  specVersion,
  contractId,
}: RelationshipsPanelProps) {
  // Phase 230.5.6 — RDF triples fetched only when contractId is set
  // so legacy callers (asset detail, dataset detail, etc.) that pass
  // structural data only continue to work without hitting the new
  // endpoint.  ``enabled: !!contractId`` keeps React Query idle
  // when the prop is absent.
  const { data: rdfData, isLoading: rdfLoading, error: rdfError } =
    useContractRelationships(contractId ?? null);

  // Collect relationships: model-level + schema-level
  const grouped: Array<{ modelName: string; rels: ContractRelationship[] }> = [];

  if (models) {
    for (const model of models) {
      if (model.relationships && model.relationships.length > 0) {
        grouped.push({ modelName: model.name, rels: model.relationships });
      }
    }
  }

  if (schemaRelationships && schemaRelationships.length > 0) {
    grouped.push({ modelName: '(schema-level)', rels: schemaRelationships });
  }

  const totalRels = grouped.reduce((n, g) => n + g.rels.length, 0);

  // Empty state
  // Phase 230.5.MetaDoD audit fix — when ``contractId`` is supplied,
  // the RDF section may have triples even when structural
  // relationships are empty (e.g. a legacy ODCS contract whose
  // semantic mappings were authored after the fact).  In that
  // case we render the main panel + the RDF section instead of
  // the structural-only empty branch.
  if (totalRels === 0 && !contractId) {
    const isOldVersion =
      specVersion &&
      !specVersion.startsWith('3.1') &&
      !specVersion.startsWith('bitol');

    return (
      <div className="relationships-panel relationships-empty">
        <h2>Relationships</h2>
        <p className="empty-message">
          No relationships defined.
          {isOldVersion && (
            <span className="empty-hint">
              {' '}
              Relationships are available in ODCS v3.1.0+.
            </span>
          )}
        </p>
      </div>
    );
  }

  return (
    <div className="relationships-panel" data-testid="relationships-panel">
      <h2>Relationships ({totalRels})</h2>

      {grouped.map(({ modelName, rels }) => (
        <div key={modelName} className="rel-group">
          <h3 className="rel-group-title">{modelName}</h3>
          <div className="table-scroll">
          <table className="rel-table">
            <thead>
              <tr>
                <th>Source fields</th>
                <th>Type</th>
                <th>Target</th>
                <th>Target fields</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {rels.map((rel, idx) => (
                <RelationshipRow key={rel.id || idx} rel={rel} />
              ))}
            </tbody>
          </table>
          </div>
        </div>
      ))}

      {/* Phase 230.5.6 — RDF triples surface (only when the panel
          is mounted with ``contractId``).  When the semantic-service
          is degraded the React Query error path catches it; when
          there are no triples we just hide the section. */}
      {contractId && (
        <RdfTriplesSection
          isLoading={rdfLoading}
          error={rdfError as Error | null}
          triples={rdfData?.triples ?? ''}
          status={rdfData?.status}
        />
      )}
    </div>
  );
}


function RdfTriplesSection({
  isLoading,
  error,
  triples,
  status,
}: {
  isLoading: boolean;
  error: Error | null;
  triples: string;
  status?: 'OK' | 'DEGRADED';
}) {
  if (isLoading) {
    return (
      <div
        className="rel-rdf-section"
        aria-busy="true"
        data-testid="relationships-rdf-loading"
      >
        <h3 className="rel-group-title">Semantic relationships</h3>
        <p>Loading semantic triples…</p>
      </div>
    );
  }
  if (error) {
    return (
      <div
        className="rel-rdf-section"
        role="alert"
        data-testid="relationships-rdf-error"
      >
        <h3 className="rel-group-title">Semantic relationships</h3>
        <p>Could not load semantic triples right now.</p>
      </div>
    );
  }
  // Empty triples → hide the whole section (the spec calls this
  // out: "render as tabular list (or graph viz)" — empty data is
  // structurally valid; just don't show an empty graph).
  const trimmed = triples.trim();
  if (!trimmed) return null;

  // Tabular rendering: split each line into (subject, predicate,
  // object) tokens.  This is best-effort N-Triples parsing — full
  // N-Triples grammar handling would require a real parser.  For
  // typical relationships the simple split is sufficient.
  const rows = trimmed
    .split('\n')
    .filter((line) => line.trim() && !line.startsWith('#'))
    .map((line, idx) => {
      const tokens = line.replace(/\s*\.\s*$/, '').split(/\s+/);
      return {
        idx,
        subject: tokens[0] ?? '',
        predicate: tokens[1] ?? '',
        object: tokens.slice(2).join(' '),
      };
    });

  return (
    <div
      className="rel-rdf-section"
      data-testid="relationships-rdf-section"
    >
      <h3 className="rel-group-title">
        Semantic relationships ({rows.length})
        {status === 'DEGRADED' && (
          <span
            className="rel-degraded-badge"
            title="Semantic service is degraded; data may be stale."
          >
            (degraded)
          </span>
        )}
      </h3>
      <div className="table-scroll">
        <table className="rel-table" data-testid="relationships-rdf-table">
          <thead>
            <tr>
              <th>Subject</th>
              <th>Predicate</th>
              <th>Object</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.idx} className="rel-row">
                <td className="rel-cell">
                  <code>{row.subject}</code>
                </td>
                <td className="rel-cell">
                  <code>{row.predicate}</code>
                </td>
                <td className="rel-cell">
                  <code>{row.object}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
