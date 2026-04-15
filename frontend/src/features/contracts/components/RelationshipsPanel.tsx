/**
 * RelationshipsPanel
 *
 * Displays contract relationships from hub_contract_json, grouped by
 * source model.  Shows an empty state for contracts without relationships
 * (pre-v3.1.0 ODCS contracts).
 */

import { Link } from 'react-router-dom';
import type { ContractRelationship, ContractSchemaObject } from '../../../shared/types/contracts';
import './RelationshipsPanel.css';

interface RelationshipsPanelProps {
  /** models[] from hub_contract_json */
  models?: ContractSchemaObject[];
  /** schema-level relationships from hub_contract_json.schema */
  schemaRelationships?: ContractRelationship[];
  /** original_spec_version for empty-state messaging */
  specVersion?: string;
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
}: RelationshipsPanelProps) {

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
  if (totalRels === 0) {
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
    <div className="relationships-panel">
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
    </div>
  );
}
