/**
 * Phase 228 F4 (228.F4.17) — admin UI for OpenLineage ingest API key
 * management.
 *
 * Endpoints:
 * * ``GET /api/v1/lineage/openlineage/keys/`` — list (admin-only)
 * * ``POST /api/v1/lineage/openlineage/keys/`` — create + return
 *   plaintext ONCE
 * * ``DELETE /api/v1/lineage/openlineage/keys/<id>/`` — revoke
 *
 * The component lives at ``/admin/integrations/openlineage`` per
 * 228.F4.19. Plaintext is shown ONCE in a dedicated copy-friendly
 * banner; subsequent renders show only the prefix + creation
 * metadata.
 */
import React, { useEffect, useState, useCallback } from 'react';

interface IngestKey {
  id: string;
  label: string;
  key_prefix: string;
  created_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  last_used_at: string | null;
  is_active: boolean;
}

interface CreateKeyResponse extends IngestKey {
  plaintext: string;
  plaintext_warning: string;
}

const KEYS_URL = '/api/v1/lineage/openlineage/keys/';

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`${resp.status}: ${text || resp.statusText}`);
  }
  return resp.json() as Promise<T>;
}

export const OpenLineageKeyManagement: React.FC = () => {
  const [keys, setKeys] = useState<IngestKey[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newLabel, setNewLabel] = useState('');
  const [justCreated, setJustCreated] = useState<CreateKeyResponse | null>(null);

  const loadKeys = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchJson<{ keys: IngestKey[] }>(KEYS_URL);
      setKeys(data.keys);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadKeys();
  }, [loadKeys]);

  const onCreate = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      try {
        const data = await fetchJson<CreateKeyResponse>(KEYS_URL, {
          method: 'POST',
          body: JSON.stringify({ label: newLabel || 'unlabeled' }),
        });
        setJustCreated(data);
        setNewLabel('');
        await loadKeys();
      } catch (err) {
        setError((err as Error).message);
      }
    },
    [newLabel, loadKeys],
  );

  const onRevoke = useCallback(
    async (id: string) => {
      // Confirmation prompt — irreversible operation; the row is
      // retained for audit but the key authenticates no further.
      const confirmed = window.confirm(
        'Revoke this OpenLineage ingest key? Subsequent requests using it will fail with 401. The audit row is retained.',
      );
      if (!confirmed) return;
      setError(null);
      try {
        const resp = await fetch(`${KEYS_URL}${id}/`, {
          method: 'DELETE',
          credentials: 'include',
        });
        if (!resp.ok) {
          throw new Error(`${resp.status}: ${await resp.text()}`);
        }
        await loadKeys();
      } catch (err) {
        setError((err as Error).message);
      }
    },
    [loadKeys],
  );

  return (
    <div className="openlineage-key-management" data-testid="openlineage-key-management">
      <h1>OpenLineage Ingest Keys</h1>
      <p className="muted">
        Per-tenant API keys for the inbound{' '}
        <code>POST /api/v1/lineage/openlineage/events/</code> endpoint.
        External producers (Marquez, Datakin, custom Airflow operators)
        send events with the <code>X-Meshant-OpenLineage-Key</code>{' '}
        header + an HMAC <code>X-Meshant-Signature</code> per the{' '}
        <a href="/docs/integrations/openlineage">integration docs</a>.
      </p>

      {error && (
        <div className="error-display" role="alert" data-testid="error-display">
          {error}
        </div>
      )}

      {justCreated && (
        <div className="just-created-banner" data-testid="new-key-banner">
          <h2>New key created — copy it now</h2>
          <p>{justCreated.plaintext_warning}</p>
          <pre className="plaintext" data-testid="plaintext">{justCreated.plaintext}</pre>
          <p>
            Prefix: <code>{justCreated.key_prefix}</code> · Label:{' '}
            <code>{justCreated.label}</code>
          </p>
          <button onClick={() => setJustCreated(null)}>I've stored it</button>
        </div>
      )}

      <form onSubmit={onCreate} className="create-key-form">
        <h2>Create new key</h2>
        <label>
          Label (e.g. "marquez-prod", "datakin-staging"){' '}
          <input
            type="text"
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            data-testid="new-key-label"
          />
        </label>
        <button type="submit" data-testid="create-key-button">
          Generate key
        </button>
      </form>

      <h2>Existing keys</h2>
      {loading && <p>Loading…</p>}
      <table className="keys-table" data-testid="keys-table">
        <thead>
          <tr>
            <th>Label</th>
            <th>Prefix</th>
            <th>Created</th>
            <th>Expires</th>
            <th>Last used</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {keys.length === 0 && !loading && (
            <tr>
              <td colSpan={7} className="empty">
                No keys yet.
              </td>
            </tr>
          )}
          {keys.map((k) => (
            <tr key={k.id} data-testid={`key-row-${k.id}`}>
              <td>{k.label}</td>
              <td>
                <code>{k.key_prefix}</code>
              </td>
              <td>{k.created_at ?? '—'}</td>
              <td>{k.expires_at ?? 'never'}</td>
              <td>{k.last_used_at ?? '—'}</td>
              <td>
                {k.revoked_at
                  ? 'revoked'
                  : k.is_active
                  ? 'active'
                  : 'expired'}
              </td>
              <td>
                {k.is_active && !k.revoked_at && (
                  <button
                    onClick={() => onRevoke(k.id)}
                    className="danger"
                    data-testid={`revoke-${k.id}`}
                  >
                    Revoke
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default OpenLineageKeyManagement;
