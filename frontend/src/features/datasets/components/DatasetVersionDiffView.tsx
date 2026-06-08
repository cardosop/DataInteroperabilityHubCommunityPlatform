/**
 * Renders schema evolution changes between two dataset versions (API `changes` array).
 */

import type { DatasetSchemaEvolutionChange } from '../../../shared/types/datasets';
import './DatasetVersionDiffView.css';

const ADDED_TYPES = new Set(['FIELD_ADDED']);
const REMOVED_TYPES = new Set(['FIELD_REMOVED']);
const MODIFIED_TYPES = new Set([
  'FIELD_TYPE_CHANGED',
  'FIELD_NULLABLE_CHANGED',
  'FIELD_PROPERTY_CHANGED',
  'PRIMARY_KEY_CHANGED',
  'UNIQUE_CONSTRAINT_CHANGED',
  'INDEX_RECOMMENDATION_CHANGED',
]);

function bucketForChangeType(type: string): 'added' | 'removed' | 'modified' | 'other' {
  if (ADDED_TYPES.has(type)) return 'added';
  if (REMOVED_TYPES.has(type)) return 'removed';
  if (MODIFIED_TYPES.has(type)) return 'modified';
  return 'other';
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

export interface DatasetVersionDiffViewProps {
  compatibilityLevel: string;
  summary: Record<string, number>;
  changes: DatasetSchemaEvolutionChange[];
  version1Label: string;
  version2Label: string;
}

export function DatasetVersionDiffView({
  compatibilityLevel,
  summary,
  changes,
  version1Label,
  version2Label,
}: DatasetVersionDiffViewProps) {
  const added = changes.filter((c) => bucketForChangeType(c.type ?? 'UNKNOWN') === 'added');
  const removed = changes.filter((c) => bucketForChangeType(c.type ?? 'UNKNOWN') === 'removed');
  const modified = changes.filter((c) => bucketForChangeType(c.type ?? 'UNKNOWN') === 'modified');
  const other = changes.filter((c) => bucketForChangeType(c.type ?? 'UNKNOWN') === 'other');

  const nonZeroSummary = Object.entries(summary).filter(([, count]) => count > 0);

  function renderTable(rows: DatasetSchemaEvolutionChange[]) {
    if (rows.length === 0) {
      return <p className="dataset-version-diff-empty">No changes in this category.</p>;
    }
    return (
      <div className="dataset-version-diff-table-wrap">
        <table className="dataset-version-diff-table">
          <thead>
            <tr>
              <th scope="col">Field</th>
              <th scope="col">Change</th>
              <th scope="col">Previous</th>
              <th scope="col">New</th>
              <th scope="col">Breaking</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={`${row.type}-${row.field_name ?? 'schema'}-${idx}`}>
                <td>{row.field_name ?? '—'}</td>
                <td>{row.description || row.type}</td>
                <td>{formatCell(row.old_value)}</td>
                <td>{formatCell(row.new_value)}</td>
                <td>{row.breaking ? <span className="dataset-version-diff-breaking">Yes</span> : 'No'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <section className="dataset-version-diff-view" data-testid="dataset-version-diff-view" aria-label="Schema comparison">
      <div className="dataset-version-diff-meta">
        <dl>
          <dt>Compared</dt>
          <dd>
            {version1Label} → {version2Label}
          </dd>
          <dt>Compatibility</dt>
          <dd>{compatibilityLevel}</dd>
          <dt>Total changes</dt>
          <dd>{changes.length}</dd>
        </dl>
      </div>

      {nonZeroSummary.length > 0 ? (
        <div data-testid="dataset-version-diff-summary">
          <strong>Summary</strong>
          <ul>
            {nonZeroSummary.map(([key, count]) => (
              <li key={key}>
                {key}: {count}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="dataset-version-diff-section" role="region" aria-label="Added fields">
        <h4>Added fields</h4>
        {renderTable(added)}
      </div>

      <div className="dataset-version-diff-section" role="region" aria-label="Removed fields">
        <h4>Removed fields</h4>
        {renderTable(removed)}
      </div>

      <div className="dataset-version-diff-section" role="region" aria-label="Modified fields">
        <h4>Modified fields</h4>
        {renderTable(modified)}
      </div>

      {other.length > 0 ? (
        <div className="dataset-version-diff-section" role="region" aria-label="Other schema changes">
          <h4>Other schema changes</h4>
          {renderTable(other)}
        </div>
      ) : null}
    </section>
  );
}
