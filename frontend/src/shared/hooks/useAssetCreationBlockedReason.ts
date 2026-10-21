/**
 * Phase 250.6.D.3 — read the asset-creation block reason from the
 * runtime capability snapshot.
 *
 * Thin wrapper over the existing ``useCapabilities`` hook so the
 * AssetTypePickerStep / AssetCreatePage can branch UX on:
 *
 *   * ``null``                    → render the normal create flow.
 *   * ``"ONBOARDING_INCOMPLETE"`` → render the picker's onboarding-CTA variant.
 *   * ``"DISABLED_BY_OPS"``       → CapabilityRoute redirects upstream.
 *
 * The hook stays read-only — it never mutates capability state. A
 * separate refresh hook would be needed to invalidate the cache;
 * for now the 5-minute TTL on the underlying service handles
 * staleness.
 */
import { useEffect, useState } from 'react';

import { capabilitiesService } from '../../features/capabilities/services/capabilitiesService';
import type { AssetCreationBlockedReason } from '../types/capabilities';

export interface AssetCreationBlockedReasonState {
  reason: AssetCreationBlockedReason;
  isLoading: boolean;
}

export function useAssetCreationBlockedReason(): AssetCreationBlockedReasonState {
  const [state, setState] = useState<AssetCreationBlockedReasonState>({
    reason: null,
    isLoading: true,
  });

  useEffect(() => {
    let cancelled = false;

    // Read from the existing in-memory cache first (cheap, sync).
    const cachedReason = capabilitiesService.getAssetCreationBlockedReason();
    if (cachedReason !== null) {
      setState({ reason: cachedReason, isLoading: false });
      return () => {
        cancelled = true;
      };
    }

    // No cached value (either no snapshot loaded yet, OR the gate is
    // open). Trigger a refresh so we converge on the current state
    // — this is a no-op if the snapshot was just loaded and is
    // valid (the underlying service handles its own caching via
    // ``loadCapabilities``).
    capabilitiesService
      .loadCapabilities()
      .then(() => {
        if (cancelled) return;
        setState({
          reason: capabilitiesService.getAssetCreationBlockedReason(),
          isLoading: false,
        });
      })
      .catch(() => {
        if (cancelled) return;
        // Fail-open: assume gate is open so the user isn't trapped
        // by a transient network failure. The backend POST gate
        // returns 403 if the gate is actually closed.
        setState({ reason: null, isLoading: false });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
