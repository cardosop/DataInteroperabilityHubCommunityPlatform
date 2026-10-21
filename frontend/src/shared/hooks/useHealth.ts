/**
 * Health React Query Hook
 */

import { useQuery } from '@tanstack/react-query';
import { healthService } from '../services/healthService';

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => healthService.getAggregateHealth(),
    refetchInterval: 30000, // Refetch every 30 seconds
    staleTime: 10000, // Consider stale after 10 seconds
    retry: 1, // Only retry once (health checks should be fast)
  });
}
