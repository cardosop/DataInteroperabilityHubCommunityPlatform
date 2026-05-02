/**
 * SPARQL Federation Allowlist Panel (Phase 230.8 / REQ-SEM-FED-001)
 *
 * Tenant-admin UI for managing the per-tenant allowlist of external
 * SPARQL endpoints reachable via SERVICE clauses.  Backed by the CRUD
 * routes at ``/api/v1/tenants/<tenant_id>/sparql-endpoints/``.
 */

import { useEffect, useState } from 'react';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { ApiError } from '../../../shared/types/api';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { tenantService, type SparqlEndpoint } from '../services/tenantService';

interface Props {
  tenantId: string;
}

export function SparqlFederationPanel({ tenantId }: Props) {
  const [endpoints, setEndpoints] = useState<SparqlEndpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [saving, setSaving] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [endpointUrl, setEndpointUrl] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [formCode, setFormCode] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await tenantService.listSparqlEndpoints(tenantId);
      setEndpoints(rows);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  };

  /* eslint-disable react-hooks/exhaustive-deps */
  useEffect(() => {
    if (tenantId) load();
  }, [tenantId]);
  /* eslint-enable react-hooks/exhaustive-deps */

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setFormCode(null);
    if (!name.trim() || !endpointUrl.trim()) {
      setFormError('Name and endpoint URL are required.');
      return;
    }
    setSaving(true);
    try {
      await tenantService.createSparqlEndpoint(tenantId, {
        name: name.trim(),
        endpoint_url: endpointUrl.trim(),
      });
      setName('');
      setEndpointUrl('');
      await load();
    } catch (err) {
      const norm = normalizeError(err);
      const code =
        (norm as { error?: { code?: string; details?: { code?: string } } })?.error?.code ??
        (norm as { error?: { details?: { code?: string } } })?.error?.details?.code ??
        null;
      const message = norm.error?.message ?? 'Failed to add endpoint';
      setFormError(message);
      setFormCode(code);
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (id: string) => {
    if (!window.confirm('Remove this SPARQL endpoint from the allowlist?')) return;
    setRemovingId(id);
    try {
      await tenantService.deleteSparqlEndpoint(tenantId, id);
      await load();
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setRemovingId(null);
    }
  };

  const handleToggleActive = async (row: SparqlEndpoint) => {
    try {
      await tenantService.patchSparqlEndpoint(tenantId, row.id, {
        is_active: !row.is_active,
      });
      await load();
    } catch (err) {
      setError(normalizeError(err));
    }
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <section className="tenant-settings-federation" data-testid="tenant-settings-federation">
      <h2>SPARQL Federation Allowlist</h2>
      <p className="tenant-settings-description">
        External SPARQL endpoints reachable via <code>SERVICE</code> clauses.
        Federated queries are blocked unless the target endpoint is active on
        this list. Loopback / link-local / RFC1918 targets are rejected by the
        SSRF guard.
      </p>

      {error && (
        <ErrorDisplay error={error} title="Failed to load endpoints" onRetry={load} />
      )}

      <form className="federation-add-form" onSubmit={handleCreate}>
        <h3>Add endpoint</h3>
        <div className="federation-add-row">
          <label>
            <span>Name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="partner-acme"
              maxLength={128}
              disabled={saving}
              data-testid="federation-add-name"
            />
          </label>
          <label>
            <span>Endpoint URL</span>
            <input
              type="url"
              value={endpointUrl}
              onChange={(e) => setEndpointUrl(e.target.value)}
              placeholder="https://sparql.partner.example.com/query"
              disabled={saving}
              data-testid="federation-add-url"
            />
          </label>
          <Button type="submit" disabled={saving} data-testid="federation-add-submit">
            {saving ? 'Adding…' : 'Add'}
          </Button>
        </div>
        {formError && (
          <div
            className="tenant-settings-error"
            role="alert"
            data-testid="federation-form-error"
          >
            {formError}
            {formCode && (
              <>
                {' '}
                <code>({formCode})</code>
              </>
            )}
          </div>
        )}
      </form>

      <div className="federation-list">
        <h3>Active endpoints ({endpoints.length})</h3>
        {endpoints.length === 0 ? (
          <p className="tenant-settings-empty">No endpoints registered.</p>
        ) : (
          <table className="federation-table" data-testid="federation-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Endpoint URL</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {endpoints.map((row) => (
                <tr key={row.id} data-testid={`federation-row-${row.id}`}>
                  <td>{row.name}</td>
                  <td>
                    <code>{row.endpoint_url}</code>
                  </td>
                  <td>{row.is_active ? 'Active' : 'Inactive'}</td>
                  <td className="federation-actions">
                    <Button
                      variant="secondary"
                      onClick={() => handleToggleActive(row)}
                      disabled={removingId === row.id}
                    >
                      {row.is_active ? 'Deactivate' : 'Activate'}
                    </Button>
                    <Button
                      variant="danger"
                      onClick={() => handleRemove(row.id)}
                      disabled={removingId === row.id}
                      data-testid={`federation-remove-${row.id}`}
                    >
                      {removingId === row.id ? 'Removing…' : 'Remove'}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
