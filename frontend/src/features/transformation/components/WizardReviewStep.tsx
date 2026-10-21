/**
 * 285.9.4.1 — WizardReviewStep sub-component.
 * 285.9b.UX.2 — ContractPreviewTable replacing raw JSON.
 * 285.9b.UX.3 — Post-scaffold guidance step.
 *
 * Final review before execution: shows contract preview or scaffold download.
 */
import React, { useEffect, useState } from 'react';
import { useTransformationApi } from '../hooks/useTransformationApi';
import type { ContractPreviewResponse } from '../hooks/useTransformationApi';

interface Props {
  direction: 'code-first' | 'contract-first' | null;
  config: Record<string, unknown>;
  pipelineId: string;
  onExecute: () => void;
  onBack: () => void;
}

interface ContractField {
  name: string;
  type?: string;
  data_type?: string;
  description?: string;
  is_primary_key?: boolean;
  is_unique?: boolean;
  is_not_null?: boolean;
}

export function WizardReviewStep({
  direction,
  config: _config,
  pipelineId,
  onExecute,
  onBack,
}: Props): React.ReactElement {
  const api = useTransformationApi();
  const [contractData, setContractData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (direction === 'code-first') {
      setLoading(true);
      api
        .getContractPreview(pipelineId)
        .then((r: { data: ContractPreviewResponse }) => setContractData(r.data?.contract ?? null))
        .catch(() => setContractData(null))
        .finally(() => setLoading(false));
    }
  }, [direction, pipelineId, api]);

  return (
    <div className="wizard-review">
      <h2>Review &amp; Execute</h2>

      {direction === 'code-first' && (
        <div>
          <p>Review the generated HubContract before executing the pipeline.</p>
          {loading ? (
            <p>Generating contract preview...</p>
          ) : contractData ? (
            <ContractPreviewTable contract={contractData} />
          ) : (
            <p>No contract data available.</p>
          )}
        </div>
      )}

      {direction === 'contract-first' && (
        <div>
          <p>Download the scaffolded dbt files and add them to your dbt project.</p>
          <button
            onClick={() =>
              api.scaffoldModel(pipelineId, '').then((r) => {
                const files = (r.data as { files: Record<string, string> }).files;
                Object.entries(files).forEach(([name, content]) => {
                  const blob = new Blob([content], { type: 'text/plain' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url; a.download = name; a.click();
                  URL.revokeObjectURL(url);
                });
              })
            }
          >
            Download Scaffold Files
          </button>

          {/* 285.9b.UX.3 — Post-scaffold guidance */}
          <div className="post-scaffold-guidance" style={{
            marginTop: '16px', padding: '12px',
            background: 'var(--color-info-bg, #eff6ff)',
            border: '1px solid var(--color-info-border, #bfdbfe)',
            borderRadius: '4px',
          }}>
            <h3>Next Steps</h3>
            <ol>
              <li>Add the downloaded files to your dbt project directory.</li>
              <li>Fill in your transformation SQL in <code>model.sql</code>.</li>
              <li>Push your changes to your git repository.</li>
              <li>Return here and click <strong>Execute Pipeline</strong>.</li>
            </ol>
          </div>
        </div>
      )}

      <div className="wizard-buttons">
        <button type="button" onClick={onBack}>Back to Configuration</button>
        <button type="button" onClick={onExecute} className="primary">
          Execute Pipeline
        </button>
      </div>
    </div>
  );
}

/** 285.9b.UX.2 — Contract preview as a proper table instead of raw JSON. */
function ContractPreviewTable({ contract }: { contract: Record<string, unknown> }) {
  const schema = contract.schema as Record<string, unknown> | undefined;
  const fields = (schema?.fields ?? []) as ContractField[];
  const primaryKeys = (schema?.primary_key ?? []) as string[];

  if (fields.length === 0) {
    return <p>No schema fields defined.</p>;
  }

  return (
    <div className="contract-preview-table">
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Nullable</th>
            <th>Description</th>
            <th>Constraints</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((f, i) => (
            <tr key={f.name ?? i}>
              <td>
                <strong>{f.name}</strong>
                {primaryKeys.includes(f.name) && (
                  <span className="pk-badge" title="Primary Key">🔑</span>
                )}
              </td>
              <td><code>{f.type ?? f.data_type ?? 'unknown'}</code></td>
              <td>{f.is_not_null ? 'NOT NULL' : 'NULL'}</td>
              <td>{f.description ?? ''}</td>
              <td>
                {f.is_unique && <span className="constraint-badge">UNIQUE</span>}
                {f.is_primary_key && <span className="constraint-badge">PK</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Tests section */}
      <section style={{ marginTop: '16px' }}>
        <h3>Tests</h3>
        <ul>
          {fields
            .filter((f) => f.is_unique || f.is_not_null || f.is_primary_key)
            .map((f, i) => (
              <li key={i}>
                <strong>{f.name}</strong>: {[
                  f.is_unique && 'unique',
                  f.is_not_null && 'not_null',
                  f.is_primary_key && 'primary_key',
                ].filter(Boolean).join(', ')}
              </li>
            ))}
        </ul>
      </section>

      {/* Metadata section */}
      <section style={{ marginTop: '16px' }}>
        <h3>Metadata</h3>
        <dl>
          <dt>Title</dt>
          <dd>{(contract.info as Record<string, string>)?.title ?? 'N/A'}</dd>
          <dt>Description</dt>
          <dd>{(contract.info as Record<string, string>)?.description ?? 'N/A'}</dd>
          <dt>Primary Keys</dt>
          <dd>{primaryKeys.length > 0 ? primaryKeys.join(', ') : 'None'}</dd>
          <dt>Total Fields</dt>
          <dd>{fields.length}</dd>
        </dl>
      </section>
    </div>
  );
}
