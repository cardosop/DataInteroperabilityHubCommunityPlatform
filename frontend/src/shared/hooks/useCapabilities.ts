/**
 * useCapabilities Hook
 * React hook for accessing capabilities
 */

import { useEffect, useState } from 'react';
import { capabilitiesService } from '../../features/capabilities/services/capabilitiesService';
import { useAuthStore } from '../../features/auth/store/authStore';
import type { CapabilitiesMap } from '../types/capabilities';

export function useCapabilities() {
  const [capabilities, setCapabilities] = useState<CapabilitiesMap>({});
  const [isLoading, setIsLoading] = useState(true);
  // W5.2 (R2-F2) — the capability cache is PER-TENANT: the hook re-runs
  // the load whenever the active tenant changes so the current tenant's
  // entry (fetched or cached) answers every consumer — a tenant switch
  // must never keep the previous tenant's capability surface mounted.
  const activeTenantId = useAuthStore((s) => s.active_tenant_id);
  const userTenantId = useAuthStore((s) => s.user?.tenant_id);

  useEffect(() => {
    let cancelled = false;
    // 30s: must exceed capabilitiesService fetch (25s + 1.5s retry) so we don't fail-open before fetch completes
    const CAPABILITIES_LOAD_TIMEOUT_MS = 30_000;
    const timeoutId = setTimeout(() => {
      // Fail-open: if capabilities take too long (e.g. backend overloaded), stop blocking auth routes
      capabilitiesService.useFallbackCapabilities();
      if (!cancelled) {
        setIsLoading(false);
      }
    }, CAPABILITIES_LOAD_TIMEOUT_MS);
    capabilitiesService.loadCapabilities().then(caps => {
      clearTimeout(timeoutId);
      if (cancelled) return;
      setCapabilities(caps);
      setIsLoading(false);
    }).catch(() => {
      clearTimeout(timeoutId);
      if (!cancelled) {
        setIsLoading(false);
      }
    });
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [activeTenantId, userTenantId]);

  const isCapabilityAvailable = (key: string): boolean => {
    return capabilitiesService.isCapabilityAvailable(key);
  };

  const getCapability = (key: string) => {
    return capabilitiesService.getCapability(key);
  };

  return {
    capabilities,
    isLoading,
    isCapabilityAvailable,
    getCapability,
  };
}
