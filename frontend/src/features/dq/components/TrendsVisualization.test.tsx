/**
 * TrendsVisualization tests — Phase 240.4.A.12.
 */
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { HttpClient } from '../../../shared/types/api';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { TrendsVisualization } from './TrendsVisualization';

describe('TrendsVisualization', () => {
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
    render(<TrendsVisualization />, { wrapper: Wrapper });
    expect(await screen.findByRole('heading', { name: /trends/i })).toBeTruthy();
  });

  it('shows the "enter an asset id" prompt before any asset is supplied', async () => {
    render(<TrendsVisualization />, { wrapper: Wrapper });
    expect(await screen.findByText(/enter an asset id/i)).toBeTruthy();
  });

  it('does not call the trends endpoint when no asset_id is set', async () => {
    render(<TrendsVisualization />, { wrapper: Wrapper });
    // Wait a tick so any spurious effect would have fired.
    await new Promise((r) => setTimeout(r, 30));
    expect(mock.get).not.toHaveBeenCalled();
  });

  it('renders the SVG chart + rows once trend data arrives', async () => {
    vi.mocked(mock.get).mockResolvedValue({
      data: {
        results: [
          {
            period_start: '2026-04-01T00:00:00Z',
            period_end: '2026-04-02T00:00:00Z',
            current_value: 92.5,
            previous_value: 90.0,
            change_amount: 2.5,
            change_percent: 2.78,
            direction: 'IMPROVING',
            trend_strength: 0.8,
            forecast_value: 93.5,
          },
          {
            period_start: '2026-04-02T00:00:00Z',
            period_end: '2026-04-03T00:00:00Z',
            current_value: 91.0,
            previous_value: 92.5,
            change_amount: -1.5,
            change_percent: -1.62,
            direction: 'DEGRADING',
            trend_strength: 0.6,
            forecast_value: 90.0,
          },
        ],
      },
    });
    render(<TrendsVisualization />, { wrapper: Wrapper });
    fireEvent.change(screen.getByLabelText(/asset id/i), {
      target: { value: 'asset-uuid-1234' },
    });
    await waitFor(() => {
      expect(screen.getByTestId('trends-chart')).toBeTruthy();
    });
    expect(screen.getByText('IMPROVING')).toBeTruthy();
    expect(screen.getByText('DEGRADING')).toBeTruthy();
  });

  it('hits the /api/v1/dq/quality/trends/ endpoint with asset_id', async () => {
    render(<TrendsVisualization />, { wrapper: Wrapper });
    fireEvent.change(screen.getByLabelText(/asset id/i), {
      target: { value: 'asset-uuid-1234' },
    });
    await waitFor(() => {
      expect(mock.get).toHaveBeenCalled();
    });
    const calledPath = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(calledPath).toContain('dq/quality/trends/');
    expect(calledPath).toContain('asset_id=asset-uuid-1234');
  });
});
