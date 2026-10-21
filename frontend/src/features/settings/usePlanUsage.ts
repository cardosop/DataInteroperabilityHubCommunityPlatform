/**
 * 285.13.11.4 — Hook for fetching tenant usage + thresholds.
 */
import { useCallback, useEffect, useState } from 'react';
import { apiClient } from '../../shared/api/client';
import type { UsageStatus } from '../../shared/types/billing';

interface UsePlanUsageResult {
  usage: UsageStatus | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function usePlanUsage(_tenantId?: string): UsePlanUsageResult {
  const [usage, setUsage] = useState<UsageStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const resp = await apiClient.getClient().get<UsageStatus>(
        '/api/v1/tenants/me/usage/',
      );
      setUsage(resp.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load usage');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  return { usage, loading, error, refetch: fetch };
}
