/**
 * 285.13.11.4 — Hook for plan upgrade/downgrade mutations.
 */
import { useCallback, useState } from 'react';
import { apiClient } from '../../shared/api/client';
import type { PlanChangeResponse } from '../../shared/types/billing';

interface UsePlanUpgradeResult {
  loading: boolean;
  error: string | null;
  success: boolean;
  upgrade: (planSlug: string) => Promise<PlanChangeResponse | null>;
  downgrade: (planSlug: string) => Promise<PlanChangeResponse | null>;
  reset: () => void;
}

export function usePlanUpgrade(): UsePlanUpgradeResult {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const doChange = useCallback(async (endpoint: string, planSlug: string) => {
    setLoading(true);
    setError(null);
    setSuccess(false);
    try {
      const resp = await apiClient.getClient().post<PlanChangeResponse>(
        endpoint,
        { plan_slug: planSlug },
      );
      setSuccess(true);
      return resp.data;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Plan change failed';
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const upgrade = useCallback(
    (slug: string) => doChange('/api/v1/tenants/me/plan/upgrade/', slug),
    [doChange],
  );
  const downgrade = useCallback(
    (slug: string) => doChange('/api/v1/tenants/me/plan/downgrade/', slug),
    [doChange],
  );
  const reset = useCallback(() => {
    setError(null);
    setSuccess(false);
  }, []);

  return { loading, error, success, upgrade, downgrade, reset };
}
