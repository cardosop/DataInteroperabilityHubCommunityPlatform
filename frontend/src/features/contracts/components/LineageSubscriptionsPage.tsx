/**
 * Phase 228.F3.14 — Lineage Subscriptions management page
 * (REQ-LIN-F3-006).
 *
 * Mounted at `/settings/subscriptions`.  Lists the current user's
 * subscriptions with controls to:
 *
 *   - Edit severity threshold + channels.
 *   - Delete (unsubscribe) a row.
 *   - Paginate via cursor (page-size = 50 from the backend).
 *
 * Capability gate: `lineage.change_notifications`.  When OFF the
 * page renders an empty-state explaining the feature is unavailable.
 *
 * No design system / no marketing copy — just the functional surface
 * a tenant admin needs to manage their subscriber inbox.
 */
import { useState } from 'react';

import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import {
  useDeleteLineageSubscription,
  useLineageSubscriptions,
  useUpdateLineageSubscription,
  type LineageSeverity,
  type LineageSubscription,
} from '../hooks/useLineageSubscriptions';
import { t } from './lineageNotificationStrings';
import './LineageSubscriptionsPage.css';

const SEVERITY_OPTIONS: LineageSeverity[] = [
  'LOW',
  'MEDIUM',
  'HIGH',
  'CRITICAL',
];

export function LineageSubscriptionsPage() {
  const { isCapabilityAvailable } = useCapabilities();
  const enabled = isCapabilityAvailable('lineage.change_notifications');
  const [cursor, setCursor] = useState<string | null>(null);
  const { data, isLoading } = useLineageSubscriptions(cursor);

  if (!enabled) {
    return (
      <main aria-label={t('lineage.notifications.page.title')}>
        <h1>{t('lineage.notifications.page.title')}</h1>
        <p>This feature is not available in your environment.</p>
      </main>
    );
  }

  return (
    <main
      aria-label={t('lineage.notifications.page.title')}
      data-testid="lineage-subscriptions-page"
    >
      <h1>{t('lineage.notifications.page.title')}</h1>
      <p>{t('lineage.notifications.page.description')}</p>

      {isLoading && <p aria-busy="true">Loading…</p>}

      {!isLoading && data && data.results.length === 0 && (
        <p data-testid="lineage-subscriptions-empty">
          {t('lineage.notifications.page.empty')}
        </p>
      )}

      {!isLoading && data && data.results.length > 0 && (
        <table className="lineage-subscriptions-table">
          <thead>
            <tr>
              <th scope="col">Source</th>
              <th scope="col">Severity</th>
              <th scope="col">In-app</th>
              <th scope="col">Email</th>
              <th scope="col">Last dispatched</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((sub) => (
              <SubscriptionRow key={sub.id} sub={sub} />
            ))}
          </tbody>
        </table>
      )}

      <nav
        className="lineage-subscriptions-pagination"
        aria-label="Subscription pagination"
      >
        {data?.previous_cursor && (
          <button
            type="button"
            onClick={() => setCursor(data.previous_cursor)}
            data-testid="lineage-subscriptions-prev"
          >
            Previous
          </button>
        )}
        {data?.next_cursor && (
          <button
            type="button"
            onClick={() => setCursor(data.next_cursor)}
            data-testid="lineage-subscriptions-next"
          >
            Next
          </button>
        )}
      </nav>
    </main>
  );
}

function SubscriptionRow({ sub }: { sub: LineageSubscription }) {
  const update = useUpdateLineageSubscription();
  const remove = useDeleteLineageSubscription();
  const [severity, setSeverity] = useState<LineageSeverity>(sub.severity_threshold);
  const [email, setEmail] = useState<boolean>(sub.email);
  const [inApp, setInApp] = useState<boolean>(sub.in_app);

  const dirty =
    severity !== sub.severity_threshold ||
    email !== sub.email ||
    inApp !== sub.in_app;

  const handleSave = () => {
    update.mutate({
      id: sub.id,
      input: { severity_threshold: severity, email, in_app: inApp },
    });
  };

  const sourceLabel = sub.source_contract
    ? `Contract ${sub.source_contract.slice(0, 8)}…`
    : sub.source_asset
      ? `Asset ${sub.source_asset.slice(0, 8)}…`
      : 'Unknown source';

  return (
    <tr data-testid={`lineage-subscription-row-${sub.id}`}>
      <td>{sourceLabel}</td>
      <td>
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value as LineageSeverity)}
          aria-label={`Severity threshold for ${sourceLabel}`}
        >
          {SEVERITY_OPTIONS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </td>
      <td>
        <input
          type="checkbox"
          checked={inApp}
          onChange={(e) => setInApp(e.target.checked)}
          aria-label={`In-app channel for ${sourceLabel}`}
        />
      </td>
      <td>
        <input
          type="checkbox"
          checked={email}
          onChange={(e) => setEmail(e.target.checked)}
          aria-label={`Email channel for ${sourceLabel}`}
        />
      </td>
      <td>{sub.last_dispatched_at ?? 'Never'}</td>
      <td>
        <button
          type="button"
          onClick={handleSave}
          disabled={!dirty || update.isPending}
          data-testid={`lineage-subscription-save-${sub.id}`}
        >
          Save
        </button>
        <button
          type="button"
          onClick={() => remove.mutate(sub.id)}
          disabled={remove.isPending}
          data-testid={`lineage-subscription-delete-${sub.id}`}
        >
          Delete
        </button>
      </td>
    </tr>
  );
}
