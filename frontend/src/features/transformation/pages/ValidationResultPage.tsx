/**
 * 285.9.4.2 — TransformationValidationResult component.
 *
 * Displays the structured diff after comparing a dbt output table
 * against its HubContract (via POST /validate-output).
 */
import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useTransformationApi } from '../hooks/useTransformationApi';
import './WizardPage.css';

interface DiffEntry {
  name: string;
  type_before?: string;
  type_after?: string;
}

interface ValidationResult {
  match: boolean;
  added: DiffEntry[];
  removed: DiffEntry[];
  changed: DiffEntry[];
  contract_name: string;
}

export function ValidationResultPage(): React.ReactElement {
  const { id: pipelineId } = useParams<{ id: string }>();
  const api = useTransformationApi();
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
    database: '',
    schemaName: '',
    tableName: '',
    warehouseType: 'snowflake',
  });

  const handleValidate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.validateOutput(pipelineId!, form);
      setResult({ match: res.data.is_valid, added: [], removed: [], changed: [], contract_name: '' });
    } catch (err: unknown) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="validation-result">
      <h1>Validate Output</h1>

      <div className="validation-form">
        <input
          placeholder="Database / Catalog"
          value={form.database}
          onChange={(e) => setForm({ ...form, database: e.target.value })}
          aria-label="Database"
        />
        <input
          placeholder="Schema"
          value={form.schemaName}
          onChange={(e) => setForm({ ...form, schemaName: e.target.value })}
          aria-label="Schema"
        />
        <input
          placeholder="Table name"
          value={form.tableName}
          onChange={(e) => setForm({ ...form, tableName: e.target.value })}
          aria-label="Table name"
        />
        <select
          value={form.warehouseType}
          onChange={(e) => setForm({ ...form, warehouseType: e.target.value })}
          aria-label="Warehouse type"
        >
          <option value="snowflake">Snowflake</option>
          <option value="bigquery">BigQuery</option>
          <option value="databricks">Databricks</option>
        </select>
        <button onClick={handleValidate} disabled={loading}>
          {loading ? 'Validating...' : 'Validate'}
        </button>
      </div>

      {error && <div role="alert">{error}</div>}

      {result && (
        <div className={`validation-summary ${result.match ? 'match' : 'mismatch'}`}>
          <h2>
            {result.match ? 'Schema matches contract' : 'Schema drift detected'}
          </h2>
          <p>Contract: {result.contract_name}</p>

          {result.added.length > 0 && (
            <section>
              <h3>Added ({result.added.length})</h3>
              <ul>
                {result.added.map((f) => (
                  <li key={f.name}>{f.name} ({f.type_after})</li>
                ))}
              </ul>
            </section>
          )}

          {result.removed.length > 0 && (
            <section>
              <h3>Removed ({result.removed.length})</h3>
              <ul>
                {result.removed.map((f) => (
                  <li key={f.name}>{f.name} ({f.type_before})</li>
                ))}
              </ul>
            </section>
          )}

          {result.changed.length > 0 && (
            <section>
              <h3>Changed ({result.changed.length})</h3>
              <ul>
                {result.changed.map((f) => (
                  <li key={f.name}>
                    {f.name}: {f.type_before} → {f.type_after}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
