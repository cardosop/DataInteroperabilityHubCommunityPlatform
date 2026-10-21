/**
 * Phase 250.6.C.1 — asset workflow-status polling hook.
 *
 * Mirrors ``useContractWorkflowStatus`` (the contracts-side hook this
 * implementation is patterned after — see
 * `frontend/src/features/contracts/hooks/useContracts.ts:184-203`)
 * but polls the asset-domain endpoint at
 * ``GET /api/v1/assets/workflows/{workflow_instance_id}/status/``
 * and applies the F2-4 polling backoff schedule:
 *
 *   * 1.5s for the first 30 seconds of RUNNING
 *   * 5s after 30 seconds
 *   * 15s after 2 minutes
 *
 * The backoff cuts wasted poll volume on long-running workflows
 * (e.g. DOWNLOAD_ALL federated import that pulls dozens of files)
 * while keeping the first-30-seconds fast-path responsive — most
 * workflows complete in under 30s, so the typical user sees the
 * 1.5s tick the whole time.
 *
 * **Memory-leak guard** (`gcTime: 60_000`): React Query keeps cache
 * entries alive for 5 minutes by default, which is wasteful for a
 * workflow status that becomes irrelevant the moment the user
 * navigates away. Setting ``gcTime: 60_000`` (1 minute) means the
 * cache entry is GC'd 60s after the last subscriber unmounts —
 * tight enough to free memory promptly without thrashing the cache
 * for users who navigate back-and-forth between the asset detail
 * page and (e.g.) the contract list.
 */
import { useQuery } from '@tanstack/react-query';

import { assetService } from '../services/assetService';
import type { AssetWorkflowStatus } from '../../../shared/types/assets';

/**
 * Time-windowed polling intervals per F2-4. Externalised as
 * constants so tests can pin the cutoff thresholds without
 * importing the hook implementation.
 */
export const POLL_INTERVAL_FAST_MS = 1500;
export const POLL_INTERVAL_MEDIUM_MS = 5000;
export const POLL_INTERVAL_SLOW_MS = 15000;
export const POLL_BACKOFF_MEDIUM_AFTER_MS = 30_000;
export const POLL_BACKOFF_SLOW_AFTER_MS = 120_000;

/**
 * Compute the next poll interval given the workflow's started_at
 * (ISO-8601) and the wall-clock now. Pure function so tests can
 * exercise the schedule without mounting the hook.
 *
 *   * elapsed < 30s   → 1.5s (fast)
 *   * elapsed < 120s  → 5s (medium)
 *   * elapsed >= 120s → 15s (slow)
 *
 * Falls back to the fast interval when ``startedAtIso`` is null
 * (e.g. the rare edge case where the workflow row has no
 * ``created_at`` — the F2-4 backoff is keyed on RUNNING duration,
 * which we can't compute without a start time).
 */
export function computePollInterval(
  startedAtIso: string | null | undefined,
  now: number = Date.now(),
): number {
  if (!startedAtIso) return POLL_INTERVAL_FAST_MS;
  const startedAt = Date.parse(startedAtIso);
  if (Number.isNaN(startedAt)) return POLL_INTERVAL_FAST_MS;
  const elapsedMs = now - startedAt;
  if (elapsedMs < POLL_BACKOFF_MEDIUM_AFTER_MS) return POLL_INTERVAL_FAST_MS;
  if (elapsedMs < POLL_BACKOFF_SLOW_AFTER_MS) return POLL_INTERVAL_MEDIUM_MS;
  return POLL_INTERVAL_SLOW_MS;
}

export interface UseAssetWorkflowStatusOptions {
  /** Disable polling without unmounting (e.g. when the parent's
   *  workflow_instance_id is known but the user is on a sub-route
   *  that doesn't render the widget). */
  enabled?: boolean;
}

/**
 * Polls the asset workflow-status endpoint with the F2-4 backoff
 * schedule. Returns the standard React Query result shape so callers
 * can read ``data`` / ``isLoading`` / ``isError`` directly.
 *
 * Polling stops automatically when the workflow reaches a terminal
 * state (``COMPLETED`` / ``FAILED``) — the ``refetchInterval`` callback
 * returns ``false`` in that case, halting the poll without unmounting
 * the hook (so the caller can still read the final ``data`` value).
 */
export function useAssetWorkflowStatus(
  workflowInstanceId: string | null | undefined,
  options: UseAssetWorkflowStatusOptions = {},
) {
  return useQuery<AssetWorkflowStatus>({
    queryKey: ['assets', 'workflows', workflowInstanceId, 'status'],
    queryFn: () => assetService.getAssetWorkflowStatus(workflowInstanceId!),
    enabled: !!workflowInstanceId && (options.enabled !== false),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.status === 'COMPLETED' || data?.status === 'FAILED') {
        return false;
      }
      return computePollInterval(data?.started_at);
    },
    // Phase 250.6.C.5 — memory-leak guard. Default React Query
    // gcTime is 5 min; tighten to 60s so a navigated-away widget's
    // cache is freed promptly.
    gcTime: 60_000,
  });
}
