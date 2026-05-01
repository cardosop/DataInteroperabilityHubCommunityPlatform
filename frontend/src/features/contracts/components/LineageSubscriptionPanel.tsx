/**
 * Phase 228.F3.13 — "Subscribe to lineage changes" button
 * (REQ-LIN-F3-006).
 *
 * Renders on contract / asset detail pages.  Visibility:
 *
 *   - Capability flag `lineage.change_notifications` is ON.
 *   - The user has read permission on the resource (the parent
 *     page handles this — if they can see this button, they can
 *     see the resource).
 *
 * State machine:
 *
 *   not-subscribed   ── Subscribe ──▶  subscribed
 *   subscribed       ── Unsubscribe ▶  not-subscribed
 *
 * The component reads the subscription list once via React Query;
 * on click it issues the POST/DELETE and re-fetches.  The hooks
 * already cache-invalidate on mutate, so the visual state flips
 * without a manual refetch.
 */
import { useState } from 'react';

import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import {
  useCreateLineageSubscription,
  useDeleteLineageSubscription,
  useLineageSubscriptions,
  type LineageSeverity,
} from '../hooks/useLineageSubscriptions';
import { t } from './lineageNotificationStrings';

export interface LineageSubscriptionPanelProps {
  /** Either source_contract OR source_asset must be set, not both. */
  sourceContractId?: string;
  sourceAssetId?: string;
}

export function LineageSubscriptionPanel({
  sourceContractId,
  sourceAssetId,
}: LineageSubscriptionPanelProps) {
  const { isCapabilityAvailable } = useCapabilities();
  const enabled = isCapabilityAvailable('lineage.change_notifications');

  const { data: list } = useLineageSubscriptions();
  const create = useCreateLineageSubscription();
  const remove = useDeleteLineageSubscription();
  const [severity, setSeverity] = useState<LineageSeverity>('HIGH');

  if (!enabled) return null;
  if (!sourceContractId && !sourceAssetId) return null;

  const existing = list?.results.find((s) =>
    sourceContractId
      ? s.source_contract === sourceContractId
      : s.source_asset === sourceAssetId,
  );

  const handleSubscribe = () => {
    create.mutate({
      source_contract: sourceContractId,
      source_asset: sourceAssetId,
      severity_threshold: severity,
      in_app: true,
    });
  };

  const handleUnsubscribe = () => {
    if (existing) remove.mutate(existing.id);
  };

  if (existing) {
    return (
      <div
        className="lineage-subscription-panel"
        data-testid="lineage-subscription-panel"
      >
        <span data-testid="lineage-subscription-status">
          {t('lineage.notifications.subscribed.status')} (
          {existing.severity_threshold}+)
        </span>
        <button
          type="button"
          onClick={handleUnsubscribe}
          disabled={remove.isPending}
          data-testid="lineage-unsubscribe"
        >
          {remove.isPending
            ? t('lineage.notifications.unsubscribing.cta')
            : t('lineage.notifications.unsubscribe.cta')}
        </button>
      </div>
    );
  }

  return (
    <div
      className="lineage-subscription-panel"
      data-testid="lineage-subscription-panel"
    >
      <label htmlFor="lineage-severity-select">
        {t('lineage.notifications.severity.label')}:
      </label>
      <select
        id="lineage-severity-select"
        value={severity}
        onChange={(e) => setSeverity(e.target.value as LineageSeverity)}
        data-testid="lineage-severity-select"
      >
        <option value="LOW">Low</option>
        <option value="MEDIUM">Medium</option>
        <option value="HIGH">High</option>
        <option value="CRITICAL">Critical</option>
      </select>
      <button
        type="button"
        onClick={handleSubscribe}
        disabled={create.isPending}
        data-testid="lineage-subscribe"
      >
        {create.isPending
          ? t('lineage.notifications.subscribing.cta')
          : t('lineage.notifications.subscribe.cta')}
      </button>
    </div>
  );
}
