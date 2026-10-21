/**
 * RootCauseAnalysisPage tests — Phase 240.4.A.12.
 */
import { type ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { HttpClient } from '../../../shared/types/api';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { RootCauseAnalysisPage } from './RootCauseAnalysisPage';

describe('RootCauseAnalysisPage', () => {
  let queryClient: QueryClient;
  let mock: HttpClient;

  function makeWrapper(initialEntries: string[] = ['/dq/rca']) {
    return function Wrapper({ children }: { children: ReactNode }) {
      return (
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={initialEntries}>
            <Routes>
              <Route path="/dq/rca" element={children} />
              <Route path="/dq/runs/:id/rca" element={children} />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      );
    };
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    mock = apiClient.getClient();
    vi.mocked(mock.get).mockResolvedValue({
      data: {
        dq_run_id: 'run-uuid-1234567890',
        analysis_date: '2026-05-01T12:00:00Z',
        root_causes: [
          {
            type: 'CHECK_FAILURE',
            description: "Check 'expect_column_values_to_not_be_null' failed",
            details: { check_name: 'expect_column_values_to_not_be_null' },
            confidence: 0.9,
          },
        ],
        primary_cause: {
          type: 'CHECK_FAILURE',
          description: "Check 'expect_column_values_to_not_be_null' failed",
          details: {},
          confidence: 0.9,
        },
        recommendations: ['Review and fix the failing check'],
      },
    });
  });

  it('renders the prompt when no DQ run / asset is supplied', async () => {
    render(<RootCauseAnalysisPage />, { wrapper: makeWrapper() });
    expect(await screen.findByText(/select a dq run/i)).toBeTruthy();
  });

  it('does not call the endpoint without an id', async () => {
    render(<RootCauseAnalysisPage />, { wrapper: makeWrapper() });
    await new Promise((r) => setTimeout(r, 30));
    expect(mock.get).not.toHaveBeenCalled();
  });

  it('hydrates the run id from the route param', async () => {
    render(<RootCauseAnalysisPage />, {
      wrapper: makeWrapper(['/dq/runs/abc12345-1111-2222-3333-444455556666/rca']),
    });
    await waitFor(() => {
      expect(mock.get).toHaveBeenCalled();
    });
    const calledPath = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(calledPath).toContain('dq/quality/root_cause_analysis/');
    expect(calledPath).toContain('dq_run_id=abc12345');
  });

  it('renders the primary cause + recommendations once loaded', async () => {
    render(<RootCauseAnalysisPage />, {
      wrapper: makeWrapper(['/dq/runs/abc12345-1111-2222-3333-444455556666/rca']),
    });
    expect(await screen.findByTestId('rca-primary-cause')).toBeTruthy();
    expect(screen.getByTestId('rca-recommendations')).toBeTruthy();
    expect(screen.getByText(/Review and fix the failing check/i)).toBeTruthy();
  });
});
