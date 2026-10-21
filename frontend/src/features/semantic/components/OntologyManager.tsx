/**
 * Phase 230.10 (REQ-SEM-ONTO-001) — Tenant Custom Ontology Manager.
 *
 * TENANT_ADMIN-only sub-tab on `/semantic`. Lists the tenant's
 * registered ontologies, supports upload (Turtle / RDF/XML / JSON-LD),
 * activate/deactivate, and delete. Validation errors from the server
 * are surfaced inline so the admin can fix and retry without
 * spelunking through job logs.
 *
 * The list endpoint excludes the heavy ``rdf_content`` field; the
 * detail-on-edit fetches the full body when the admin clicks "View".
 */
import { useEffect, useState } from 'react';

import { apiClient } from '../../../shared/api/client';
import { Button } from '../../../shared/components/Button';
import { useAuthStore } from '../../auth/store/authStore';

interface TenantOntologyRow {
  id: string;
  name: string;
  namespace_iri: string;
  format: 'turtle' | 'rdf_xml' | 'json_ld';
  triple_count: number;
  validation_status: 'PENDING' | 'VALIDATING' | 'VALID' | 'INVALID' | 'LOAD_FAILED';
  validation_errors: { code: string; message: string }[] | null;
  is_active: boolean;
  activated_at: string | null;
  created_at: string;
  updated_at: string;
  named_graph_uri: string;
}

interface UploadFormState {
  name: string;
  namespace_iri: string;
  format: 'turtle' | 'rdf_xml' | 'json_ld';
  rdf_content: string;
}

const INITIAL_FORM: UploadFormState = {
  name: '',
  namespace_iri: '',
  format: 'turtle',
  rdf_content: '',
};


export function OntologyManager() {
  const user = useAuthStore((s) => s.user);
  const isTenantAdmin = !!user && (user.is_platform_admin || (user.roles ?? []).includes('TENANT_ADMIN'));

  const [rows, setRows] = useState<TenantOntologyRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<UploadFormState>(INITIAL_FORM);
  const [submitting, setSubmitting] = useState(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiClient.getClient().get<{ results?: TenantOntologyRow[] } | TenantOntologyRow[]>(
        '/semantic/ontologies/',
      );
      const data = resp.data;
      const list = Array.isArray(data) ? data : data.results ?? [];
      setRows(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load ontologies');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (isTenantAdmin) refresh();
  }, [isTenantAdmin]);

  if (!isTenantAdmin) {
    return (
      <div className="semantic-tab-content" data-testid="ontology-manager-forbidden">
        <p>Custom ontology management requires the TENANT_ADMIN role.</p>
      </div>
    );
  }

  async function handleUpload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await apiClient.getClient().post('/semantic/ontologies/', form);
      setForm(INITIAL_FORM);
      await refresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggle(row: TenantOntologyRow) {
    setError(null);
    try {
      await apiClient.getClient().patch(`/semantic/ontologies/${row.id}/`, {
        is_active: !row.is_active,
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Toggle failed');
    }
  }

  async function handleDelete(row: TenantOntologyRow) {
    if (!confirm(`Delete ontology "${row.name}"? This drops the named graph from Fuseki.`)) {
      return;
    }
    setError(null);
    try {
      await apiClient.getClient().delete(`/semantic/ontologies/${row.id}/`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    }
  }

  return (
    <div className="semantic-tab-content" data-testid="ontology-manager">
      <h3>Custom Ontologies</h3>
      <p style={{ color: 'var(--color-neutral-700)', marginBottom: 'var(--spacing-md)' }}>
        Upload Turtle / RDF/XML / JSON-LD ontologies to extend the SPARQL vocabulary
        available to your tenant. Validation runs at upload; activation loads the
        ontology into Fuseki at <code>urn:tenant:&lt;id&gt;:ontology:&lt;name&gt;</code>.
      </p>

      {error && (
        <div role="alert" style={{ color: 'var(--color-danger-700)' }} data-testid="ontology-error">
          {error}
        </div>
      )}

      <form onSubmit={handleUpload} data-testid="ontology-upload-form" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
          <input
            type="text"
            placeholder="name (e.g. acme)"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            data-testid="ontology-name-input"
            required
          />
          <input
            type="url"
            placeholder="https://acme.example/ontology/"
            value={form.namespace_iri}
            onChange={(e) => setForm({ ...form, namespace_iri: e.target.value })}
            data-testid="ontology-namespace-input"
            required
          />
          <select
            value={form.format}
            onChange={(e) =>
              setForm({ ...form, format: e.target.value as UploadFormState['format'] })
            }
            data-testid="ontology-format-select"
            aria-label="Select ontology format"
          >
            <option value="turtle">Turtle</option>
            <option value="rdf_xml">RDF/XML</option>
            <option value="json_ld">JSON-LD</option>
          </select>
        </div>
        <textarea
          placeholder="@prefix acme: <https://acme.example/ontology/> . ..."
          value={form.rdf_content}
          onChange={(e) => setForm({ ...form, rdf_content: e.target.value })}
          rows={8}
          style={{ width: '100%', marginTop: '0.5rem', fontFamily: 'monospace' }}
          data-testid="ontology-content-input"
          required
        />
        <Button type="submit" disabled={submitting} data-testid="ontology-upload-button">
          {submitting ? 'Uploading…' : 'Upload'}
        </Button>
      </form>

      {loading && <p>Loading ontologies…</p>}
      {!loading && rows.length === 0 && (
        <p data-testid="ontology-empty">No custom ontologies yet.</p>
      )}
      {rows.length > 0 && (
        <table data-testid="ontology-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th align="left">Name</th>
              <th align="left">Namespace</th>
              <th align="right">Triples</th>
              <th align="left">Status</th>
              <th align="left">Active</th>
              <th align="left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} data-testid={`ontology-row-${r.name}`}>
                <td>{r.name}</td>
                <td>
                  <code>{r.namespace_iri}</code>
                </td>
                <td align="right">{r.triple_count}</td>
                <td>{r.validation_status}</td>
                <td>{r.is_active ? 'Yes' : 'No'}</td>
                <td>
                  <Button
                    variant="ghost"
                    onClick={() => handleToggle(r)}
                    disabled={r.validation_status !== 'VALID' && !r.is_active}
                    data-testid={`ontology-toggle-${r.name}`}
                  >
                    {r.is_active ? 'Deactivate' : 'Activate'}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => handleDelete(r)}
                    data-testid={`ontology-delete-${r.name}`}
                  >
                    Delete
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
