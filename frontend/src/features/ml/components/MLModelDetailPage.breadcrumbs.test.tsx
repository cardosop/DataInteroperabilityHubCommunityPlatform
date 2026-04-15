/**
 * MLModelDetailPage — 222.2.2 breadcrumbs gap-closure test.
 *
 * Real page + real React Query; only apiClient HTTP seam is auto-mocked.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { MLModelDetailPage } from './MLModelDetailPage';

describe('MLModelDetailPage breadcrumbs', () => {
  let queryClient: QueryClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/ml/models/model-abc']}>
          <Routes>
            <Route path="/ml/models/:id" element={children} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: {
        id: 'model-abc',
        odh_model_name: 'Sentiment Classifier',
        odh_model_version: '1.0.0',
        model_type: 'classification',
        status: 'READY',
        created_at: '2026-04-01T00:00:00Z',
      },
    } as never);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders Home → ML → model name', async () => {
    render(<MLModelDetailPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByLabelText('Breadcrumb')).toBeInTheDocument();
    });
    const nav = screen.getByLabelText('Breadcrumb');
    expect(nav).toHaveTextContent(/Home/);
    expect(nav).toHaveTextContent(/ML/);
    expect(nav).toHaveTextContent(/Sentiment Classifier/);
  });
});
