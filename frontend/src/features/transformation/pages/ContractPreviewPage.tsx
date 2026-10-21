/**
 * 285.9.4.2 — TransformationContractPreview component.
 *
 * Displays a HubContract JSON preview generated from dbt model YAML
 * and/or catalog.json for a given pipeline.
 */
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useTransformationApi } from '../hooks/useTransformationApi';
import './WizardPage.css';

interface ContractPreviewData {
  contract: Record<string, unknown>;
  pipeline_id: string;
  source: string;
}

export function ContractPreviewPage(): React.ReactElement {
  const { id: pipelineId } = useParams<{ id: string }>();
  const api = useTransformationApi();
  const [data, setData] = useState<ContractPreviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getContractPreview(pipelineId!)
      .then((result) => {
        if (!cancelled) setData(result.data as unknown as ContractPreviewData);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [pipelineId, api]);

  if (loading) return <div aria-busy="true">Generating contract preview...</div>;
  if (error) return <div role="alert">{error}</div>;
  if (!data) return <div>No contract data available.</div>;

  const fields: Record<string, unknown>[] = (data.contract as Record<string, unknown>)?.schema
    ? (data.contract as Record<string, Record<string, unknown[]>>).schema.fields as Record<string, unknown>[]
    : ([] as Record<string, unknown>[]);

  return (
    <div className="contract-preview">
      <h1>Contract Preview</h1>
      <p>Source: {data.source}</p>

      {Array.isArray(fields) && fields.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Description</th>
              <th>Constraints</th>
            </tr>
          </thead>
          <tbody>
            {fields.map((f: Record<string, unknown>, i: number) => (
              <tr key={f.name as string ?? i}>
                <td>{f.name as string}</td>
                <td><code>{(f.type ?? f.data_type) as string}</code></td>
                <td>{(f.description as string) ?? ''}</td>
                <td>
                  {f.is_primary_key ? 'PK ' : ''}
                  {f.is_unique ? 'UNIQUE ' : ''}
                  {f.is_not_null ? 'NOT NULL' : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>No schema fields defined. Run dbt docs generate to populate the contract.</p>
      )}
    </div>
  );
}
