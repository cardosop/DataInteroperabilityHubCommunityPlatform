/**
 * Phase 278.R.6 — ProductTour gate component.
 *
 * Mounts the ProductTour overlay only when:
 * 1. UX v2 is enabled for the tenant (useUxV2Gate)
 * 2. The user has not yet seen the tour (!has_seen_tour)
 *
 * On tour completion, persists the flag to localStorage (immediate gate)
 * and to the backend via PATCH /auth/me/ (cross-device persistence).
 *
 * Renders nothing when the gate conditions are not met, so the common-case
 * render cost is two hook subscriptions.
 */
import { useCallback } from 'react';
import { useAuthStore } from '../../auth/store/authStore';
import { authService } from '../../auth/services/authService';
import { usePersona } from '../../home/hooks/usePersona';
import { useUxV2Gate } from '../../../shared/hooks/useUxV2Gate';
import { ProductTour } from './ProductTour';

export function ProductTourGate() {
  const persona = usePersona();
  const { enabled: uxV2, isLoading: gateLoading } = useUxV2Gate();
  const { user, refreshUser } = useAuthStore();
  const hasSeenTour = user?.has_seen_tour ?? false;

  const handleComplete = useCallback(async () => {
    try {
      // Persist to backend for cross-device consistency
      const updated = await authService.updateProfile({ has_seen_tour: true });
      // Sync the store with the full /auth/me/ response
      refreshUser(updated);
    } catch {
      // Best-effort: the localStorage flag inside ProductTour is the
      // immediate gate; backend persistence is a background concern.
    }
  }, [refreshUser]);

  // Don't render while gate is loading — avoids flash of tour on ux_v2 tenants
  // where the capabilities query hasn't resolved yet.
  if (gateLoading) return null;

  // Gate: UX v2 must be enabled AND user must not have seen the tour
  if (!uxV2 || hasSeenTour) return null;

  return <ProductTour persona={persona} onComplete={handleComplete} />;
}
