/**
 * Phase 231.5 — Regulation-level summary rows from `regulation_summaries` (mapping `regulation_summary`).
 */

import type { ComplianceRegulationSummaryRow } from '../../../shared/types/compliance';

export interface RegulationSummaryTableProps {
  /**
   * Wire value from GET …/results/ `regulation_summaries` (normally list or null).
   * Declared `unknown` so non-array shapes are handled without unsafe casts at the call site.
   */
  rows: unknown;
}

/** Extra numeric / string columns beyond the canonical trio (union across rows). */
function extraColumns(rows: ComplianceRegulationSummaryRow[]): string[] {
  const reserved = new Set(['regulation', 'status', 'violations']);
  const keys = new Set<string>();
  for (const row of rows) {
    for (const k of Object.keys(row)) {
      if (!reserved.has(k)) keys.add(k);
    }
  }
  return [...keys].sort();
}

export function RegulationSummaryTable({ rows }: RegulationSummaryTableProps) {
  if (rows == null || !Array.isArray(rows) || rows.length === 0) {
    return null;
  }

  const safeRows = rows.filter(
    (r): r is ComplianceRegulationSummaryRow =>
      r != null &&
      typeof r === 'object' &&
      typeof (r as { regulation?: unknown }).regulation === 'string'
  );

  if (safeRows.length === 0) {
    return null;
  }

  const extras = extraColumns(safeRows);

  return (
    <section className="phase19-regulation-summary" data-testid="regulation-summary-table-section">
      <h3 className="phase19-section-title">Regulation summary</h3>
      <div className="phase19-table-scroll">
        <table className="phase19-reg-table" data-testid="regulation-summary-table">
          <thead>
            <tr>
              <th scope="col">Regulation</th>
              <th scope="col">Status</th>
              <th scope="col">Violations</th>
              {extras.map((c) => (
                <th key={c} scope="col">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {safeRows.map((row, idx) => (
              // regulation + row index stays stable enough for keyed rows without server id
              <tr key={`${row.regulation}-${idx}`}>
                <td>{row.regulation}</td>
                <td>{row.status ?? '—'}</td>
                <td>{row.violations != null ? row.violations : '—'}</td>
                {extras.map((c) => (
                  <td key={c}>{formatCell((row as unknown as Record<string, unknown>)[c])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatCell(value: unknown): string {
  if (value == null) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}
