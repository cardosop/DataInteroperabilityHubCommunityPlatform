/**
 * ScorecardsExecutiveDashboard tests — Phase 240.4.A.12.
 */
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { HttpClient } from '../../../shared/types/api';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { ScorecardsExecutiveDashboard } from './ScorecardsExecutiveDashboard';

describe('ScorecardsExecutiveDashboard', () => {
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
    // Default: tenant-level executive dashboard payload.
    vi.mocked(mock.get).mockResolvedValue({
      data: {
        period: { start: '2026-04-01T00:00:00Z', end: '2026-05-01T00:00:00Z', days: 30 },
        summary: {
          total_runs: 12,
          avg_quality_score: 88.4,
          pass_rate: 75.0,
          fail_rate: 8.3,
          warn_count: 2,
        },
        score_distribution: { excellent: 5, good: 4, fair: 2, poor: 1, critical: 0 },
        top_issues: [{ issue: 'expect_column_values_to_not_be_null:FAIL', count: 3, percentage: 25.0 }],
        trend_summary: {
          improving: 3,
          degrading: 1,
          stable: 8,
          improving_percent: 25.0,
          degrading_percent: 8.3,
        },
      },
    });
  });

  it('renders heading + filters without crashing', async () => {
    render(<ScorecardsExecutiveDashboard />, { wrapper: Wrapper });
    expect(await screen.findByRole('heading', { name: /scorecards/i })).toBeTruthy();
  });

  it('renders the tenant executive dashboard when no asset_id is supplied', async () => {
    render(<ScorecardsExecutiveDashboard />, { wrapper: Wrapper });
    expect(await screen.findByTestId('executive-dashboard')).toBeTruthy();
    expect(screen.getByText('12')).toBeTruthy();
  });

  it('switches to asset scorecard view when asset_id is supplied', async () => {
    render(<ScorecardsExecutiveDashboard />, { wrapper: Wrapper });
    // Switch the mock response BEFORE the asset-id-driven refetch.
    vi.mocked(mock.get).mockResolvedValue({
      data: {
        asset_id: 'asset-uuid-1234',
        period: { start: '2026-04-01T00:00:00Z', end: '2026-05-01T00:00:00Z', days: 30 },
        metrics: {
          total_runs: 4,
          avg_quality_score: 92.1,
          pass_rate: 100.0,
          fail_rate: 0.0,
        },
        recent_runs: [],
        trends: [],
      },
    });
    fireEvent.change(screen.getByLabelText(/asset id/i), {
      target: { value: 'asset-uuid-1234' },
    });
    await waitFor(() => {
      expect(screen.getByTestId('asset-scorecard')).toBeTruthy();
    });
    expect(screen.getByText('asset-uuid-1234')).toBeTruthy();
  });

  it('hits the /api/v1/dq/quality/scorecards/ endpoint', async () => {
    render(<ScorecardsExecutiveDashboard />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(mock.get).toHaveBeenCalled();
    });
    const calledPath = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(calledPath.startsWith('dq/quality/scorecards/')).toBe(true);
  });
});
