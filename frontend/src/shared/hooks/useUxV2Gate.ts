/**
 * useUxV2Gate — tenant feature flag for UX v2 staged rollout (278.M.4).
 *
 * Reads the ``ux_v2`` capability from the capabilities endpoint.
 * When false (default for existing tenants), v2 surfaces are hidden
 * and the classic UX renders without data loss.
 */
import { useCapabilities } from './useCapabilities';

export function useUxV2Gate(): {
  /** Whether UX v2 surfaces should render for this tenant. */
  enabled: boolean;
  /** True while the capabilities query is loading. */
  isLoading: boolean;
} {
  const { isCapabilityAvailable, isLoading } = useCapabilities();

  return {
    enabled: isCapabilityAvailable('ux_v2'),
    isLoading,
  };
}

/**
 * Return a component or element only when UX v2 is enabled.
 * Graceful fallback — when disabled, the classic UX renders unchanged.
 */
export function uxV2Only<T>(enabled: boolean, v2Content: T, fallback?: T): T | null {
  if (enabled) return v2Content;
  return fallback ?? null;
}
