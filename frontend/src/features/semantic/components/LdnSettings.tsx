/**
 * Phase 230.12.12 (REQ-SEM-LDN-001) — LDN settings UI.
 *
 * TENANT_ADMIN-only sub-tab on `/semantic`. Lists incoming inbox
 * notifications + outbound subscriptions, with actions to register
 * a new partner key and to subscribe to a partner inbox.
 */
import { useEffect, useState } from 'react';

import { apiClient } from '../../../shared/api/client';
import { Button } from '../../../shared/components/Button';
import { useAuthStore } from '../../auth/store/authStore';

interface InboxRow {
  id: string;
  target_iri: string;
  source_url: string;
  payload_format: string;
  received_at: string;
  status: string;
  signature_verified: boolean;
  signature_key_id: string;
  source_ip: string;
}

export function LdnSettings() {
  const user = useAuthStore((s) => s.user);
  const tenantId = user?.tenant_id ?? '';
  const isTenantAdmin =
    !!user && (user.is_platform_admin || (user.roles ?? []).includes('TENANT_ADMIN'));

  const [inbox, setInbox] = useState<InboxRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [subscribeUrl, setSubscribeUrl] = useState('');
  const [subscribeType, setSubscribeType] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function refreshInbox() {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getClient().get<InboxRow[]>(
        `/semantic/ldn/inbox/${tenantId}/`,
      );
      setInbox(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load inbox');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (isTenantAdmin) refreshInbox();
  }, [isTenantAdmin, tenantId]);

  async function handleSubscribe(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await apiClient.getClient().post('/semantic/ldn/subscriptions/', {
        target_inbox_url: subscribeUrl,
        resource_type_filter: subscribeType,
        is_active: true,
      });
      setSubscribeUrl('');
      setSubscribeType('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Subscribe failed');
    } finally {
      setSubmitting(false);
    }
  }

  if (!isTenantAdmin) {
    return (
      <div className="semantic-tab-content" data-testid="ldn-settings-forbidden">
        <p>LDN settings require the TENANT_ADMIN role.</p>
      </div>
    );
  }

  return (
    <div className="semantic-tab-content" data-testid="ldn-settings">
      <h3>Linked Data Notifications</h3>
      <p style={{ color: 'var(--color-neutral-700)', marginBottom: 'var(--spacing-md)' }}>
        Inbox URL: <code>/api/v1/semantic/ldn/inbox/{tenantId}</code>
        <br />
        Partners send signed RDF notifications here. Outbound deliveries fire
        on Asset / Contract / Dataset updates per active subscription.
      </p>

      {error && (
        <div role="alert" style={{ color: 'var(--color-danger-700)' }} data-testid="ldn-error">
          {error}
        </div>
      )}

      <h4>Outbound subscription</h4>
      <form onSubmit={handleSubscribe} data-testid="ldn-subscribe-form">
        <input
          type="url"
          placeholder="https://partner.example/ldn/inbox"
          value={subscribeUrl}
          onChange={(e) => setSubscribeUrl(e.target.value)}
          required
          data-testid="ldn-subscribe-url-input"
        />
        <select
          value={subscribeType}
          onChange={(e) => setSubscribeType(e.target.value)}
          data-testid="ldn-subscribe-type-select"
          aria-label="Filter by resource type"
        >
          <option value="">All resource types</option>
          <option value="asset">Asset</option>
          <option value="contract">Contract</option>
          <option value="dataset">Dataset</option>
        </select>
        <Button type="submit" disabled={submitting} data-testid="ldn-subscribe-button">
          {submitting ? 'Subscribing…' : 'Subscribe'}
        </Button>
      </form>

      <h4>Recent inbox notifications</h4>
      {loading && <p>Loading…</p>}
      {!loading && inbox.length === 0 && (
        <p data-testid="ldn-inbox-empty">No notifications received yet.</p>
      )}
      {inbox.length > 0 && (
        <table data-testid="ldn-inbox-table" style={{ width: '100%' }}>
          <thead>
            <tr>
              <th align="left">Received</th>
              <th align="left">From (key_id)</th>
              <th align="left">Source IP</th>
              <th align="left">Format</th>
              <th align="left">Status</th>
              <th align="left">Verified</th>
            </tr>
          </thead>
          <tbody>
            {inbox.map((r) => (
              <tr key={r.id}>
                <td>{new Date(r.received_at).toISOString()}</td>
                <td>
                  <code>{r.signature_key_id}</code>
                </td>
                <td>{r.source_ip}</td>
                <td>{r.payload_format}</td>
                <td>{r.status}</td>
                <td>{r.signature_verified ? 'Yes' : 'No'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
