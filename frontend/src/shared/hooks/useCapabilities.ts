/**
 * useCapabilities Hook
 * React hook for accessing capabilities
 */

import { useEffect, useState } from 'react';
import { capabilitiesService } from '../../features/capabilities/services/capabilitiesService';
import type { CapabilitiesMap } from '../types/capabilities';

export function useCapabilities() {
  const [capabilities, setCapabilities] = useState<CapabilitiesMap>({});
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // 30s: must exceed capabilitiesService fetch (25s + 1.5s retry) so we don't fail-open before fetch completes
    const CAPABILITIES_LOAD_TIMEOUT_MS = 30_000;
    const timeoutId = setTimeout(() => {
      // Fail-open: if capabilities take too long (e.g. backend overloaded), stop blocking auth routes
      capabilitiesService.useFallbackCapabilities();
      setIsLoading(false);
    }, CAPABILITIES_LOAD_TIMEOUT_MS);
    capabilitiesService.loadCapabilities().then(caps => {
      clearTimeout(timeoutId);
      setCapabilities(caps);
      setIsLoading(false);
    }).catch(() => {
      clearTimeout(timeoutId);
      setIsLoading(false);
    });
  }, []);

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
