/**
 * AnomaliesDashboard tests — Phase 240.4.A.12.
 *
 * Mocks ``shared/api/client`` (one level under dqService) so the
 * React Query hook + service composition is exercised end-to-end with
 * a real ``QueryClient``.  No mocks of business logic.
 */
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { HttpClient } from '../../../shared/types/api';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { AnomaliesDashboard } from './AnomaliesDashboard';

describe('AnomaliesDashboard', () => {
  let queryClient: QueryClient;
  let mock: HttpClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    mock = apiClient.getClient();
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
  });

  it('renders heading + filters without crashing', async () => {
    render(<AnomaliesDashboard />, { wrapper: Wrapper });
    expect(await screen.findByRole('heading', { name: /anomalies/i })).toBeTruthy();
  });

  it('renders empty state when no anomalies are returned', async () => {
    render(<AnomaliesDashboard />, { wrapper: Wrapper });
    expect(await screen.findByTestId('empty-state-title')).toBeTruthy();
  });

  it('renders rows from the anomalies endpoint', async () => {
    vi.mocked(mock.get).mockResolvedValue({
      data: {
        results: [
          {
            id: 'anom-1',
            tenant_id: 't-1',
            asset_id: 'asset-1',
            dataset_id: null,
            dq_run_id: 'run-1',
            metric_type: 'quality_score',
            expected_value: 95.0,
            actual_value: 70.0,
            deviation: -25.0,
            severity: 'HIGH',
            anomaly_type: 'sudden_drop',
            description: 'Quality score dropped 26%',
            metadata: {},
            detected_at: '2026-05-01T12:00:00Z',
            acknowledged: false,
          },
        ],
      },
    });
    render(<AnomaliesDashboard />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByText('Quality score dropped 26%')).toBeTruthy();
    });
  });

  it('hits the canonical /api/v1/dq/quality/anomalies/ endpoint', async () => {
    render(<AnomaliesDashboard />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(mock.get).toHaveBeenCalled();
    });
    const calledPath = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(calledPath.startsWith('dq/quality/anomalies/')).toBe(true);
  });

  it('renders a CSV export button', async () => {
    render(<AnomaliesDashboard />, { wrapper: Wrapper });
    expect(await screen.findByRole('button', { name: /csv|export/i })).toBeTruthy();
  });
});
