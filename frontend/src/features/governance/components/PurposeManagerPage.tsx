/**
 * TENANT_ADMIN — CRUD consent purposes (Phase 232.1).
 */
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../../../shared/api/client';

type Purpose = {
  id: string;
  key: string;
  name: string;
  description: string;
  is_active: boolean;
  iab_purpose_id?: string;
};

export function PurposeManagerPage() {
  const [items, setItems] = useState<Purpose[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const { data } = await apiClient.getClient().get<{ results?: Purpose[] } | Purpose[]>(
        '/api/v1/governance/consent-purposes/',
      );
      const rows = Array.isArray(data) ? data : (data.results ?? []);
      setItems(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load purposes');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onCreate = async () => {
    const key = window.prompt('Purpose key (slug, e.g. marketing.email)', 'marketing.email');
    if (!key) return;
    const name = window.prompt('Display name', 'Marketing email') || key;
    setBusy(true);
    setError(null);
    try {
      // ``apiClient.baseURL`` is ``/api/v1`` — pass the relative path
      // only, otherwise the request lands at ``/api/v1/api/v1/…`` and
      // 404s. Mirrors the convention used by every other caller in
      // this file and across the SPA.
      await apiClient.getClient().post('governance/consent-purposes/', {
        key,
        name,
        description: '',
        is_active: true,
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Create failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="governance-consent-purposes" style={{ padding: '1.5rem' }}>
      <p>
        <Link to="/governance">← Back to governance</Link>
      </p>
      <h1>Consent purposes</h1>
      <p>Define processing purposes (TCF metadata optional). Requires TENANT_ADMIN.</p>
      {error ? <p role="alert">{error}</p> : null}
      <button type="button" disabled={busy} onClick={() => void onCreate()}>
        Add purpose
      </button>
      <ul>
        {items.map((p) => (
          <li key={p.id}>
            <strong>{p.key}</strong> — {p.name} {p.is_active ? '' : '(inactive)'}
            {p.iab_purpose_id ? ` [IAB ${p.iab_purpose_id}]` : ''}
          </li>
        ))}
      </ul>
    </div>
  );
}
