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
    capabilitiesService.loadCapabilities().then(caps => {
      setCapabilities(caps);
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
