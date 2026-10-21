/**
 * SPARQLResultTable — renders SPARQL JSON result bindings as a table.
 */

import './SPARQLResultTable.css';

interface Binding {
  [variable: string]: { value: string; type?: string; datatype?: string } | undefined;
}

export interface SPARQLResultTableProps {
  vars: string[];
  bindings: Binding[];
}

export function SPARQLResultTable({ vars, bindings }: SPARQLResultTableProps) {
  return (
    <div className="sparql-result-table-wrapper" data-testid="sparql-result-table">
      <table className="sparql-result-table">
        <thead>
          <tr>
            {vars.map((v) => (
              <th key={v}>{v}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bindings.map((row, idx) => (
            <tr key={idx}>
              {vars.map((v) => (
                <td key={v} title={row[v]?.datatype}>
                  {row[v]?.value ?? ''}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
