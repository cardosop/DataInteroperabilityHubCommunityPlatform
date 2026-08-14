/**
 * 302.5 — Service status indicator for app shell header.
 *
 * Reads ``GET /api/v1/health/?include=downstream`` and renders a
 * green / yellow / red dot in the app header to show platform health.
 *
 * States:
 *   - healthy (green):     all downstream services healthy
 *   - degraded (yellow):   one or more services degraded or unreachable
 *   - error (red):         health endpoint itself unreachable
 *   - loading (neutral):   initial fetch in flight
 */
import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';

interface DownstreamStatus {
  status: 'healthy' | 'degraded' | 'unreachable';
  healthy: number;
  total: number;
  services: Record<string, { status: string }>;
}

type IndicatorState = 'loading' | 'healthy' | 'degraded' | 'error';

const COLORS: Record<IndicatorState, string> = {
  loading: 'bg-gray-400',
  healthy: 'bg-green-500',
  degraded: 'bg-yellow-500',
  error: 'bg-red-500',
};

const LABELS: Record<IndicatorState, string> = {
  loading: 'Checking platform health…',
  healthy: 'All services healthy',
  degraded: 'Some services degraded',
  error: 'Health endpoint unreachable',
};

export const ServiceStatusIndicator: React.FC = () => {
  const [state, setState] = useState<IndicatorState>('loading');
  const [details, setDetails] = useState<DownstreamStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    let interval: ReturnType<typeof setInterval>;

    async function check() {
      try {
        const resp = await apiClient.getClient().get<{
          downstream?: DownstreamStatus;
        }>('/api/v1/health/?include=downstream');
        if (cancelled) return;
        const ds = resp.data?.downstream;
        setDetails(ds || null);
        setState(ds?.status === 'healthy' ? 'healthy' : 'degraded');
      } catch {
        if (cancelled) return;
        setState('error');
      }
    }

    check();
    interval = setInterval(check, 60_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <span
      className="service-status-indicator"
      title={LABELS[state]}
      aria-label={LABELS[state]}
      data-testid="service-status-indicator"
      data-status={state}
    >
      <span
        className={`inline-block w-2.5 h-2.5 rounded-full ${COLORS[state]} ${state === 'loading' ? 'animate-pulse' : ''}`}
        aria-hidden="true"
      />
      {details && state === 'degraded' && (
        <span className="sr-only">
          {details.healthy} of {details.total} services healthy
        </span>
      )}
    </span>
  );
};
