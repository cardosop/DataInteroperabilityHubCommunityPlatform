/**
 * DatasetVersionsPage — compare-flow pins the Phase 260.3.A testid contract
 * (dataset-version-compare-toggle / -select-1 / -select-2 / -submit) and the
 * schema-evolution response shape from
 * GET /datasets/{id}/versions/compare/ rendered via DatasetVersionDiffView.
 */

import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { DatasetVersionsPage } from './DatasetVersionsPage';

const V1 = {
  id: '11111111-1111-1111-1111-111111111111',
  version: '1.0.0',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  size_bytes: 1024,
};

const V2 = {
  id: '22222222-2222-2222-2222-222222222222',
  version: '1.1.0',
  created_at: '2026-01-02T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
  size_bytes: 2048,
};

describe('DatasetVersionsPage', () => {
  let queryClient: QueryClient;
  let mock: HttpClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/datasets/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/versions']}>
          <Routes>
            <Route path="/datasets/:id/versions" element={children} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    mock = apiClient.getClient();
    vi.mocked(mock.get).mockImplementation(async (url: string) => {
      const target = String(url);
      if (target.includes('/versions/compare/')) {
        return {
          data: {
            version1: V1,
            version2: V2,
            compatibility_level: 'BACKWARD_COMPATIBLE',
            summary: { FIELD_ADDED: 1 },
            changes: [
              {
                type: 'FIELD_ADDED',
                field_name: 'region',
                description: "Field 'region' added",
                breaking: false,
                old_value: null,
                new_value: { name: 'region' },
              },
            ],
          },
        };
      }
      if (target.includes('/versions/')) {
        return { data: [V1, V2] };
      }
      return { data: { id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', name: 'Test dataset' } };
    });
  });

  it('toggle opens the compare form and submit renders the schema-evolution diff view', async () => {
    render(<DatasetVersionsPage />, { wrapper: Wrapper });

    // The toggle renders only once the versions fetch resolves.
    const toggle = await screen.findByTestId('dataset-version-compare-toggle');
    fireEvent.click(toggle);

    const select1 = screen.getByTestId('dataset-version-compare-select-1');
    const select2 = screen.getByTestId('dataset-version-compare-select-2');
    expect(select1).toBeInTheDocument();
    expect(select2).toBeInTheDocument();

    // Options carry version ids (the compare endpoint's query params).
    fireEvent.change(select1, { target: { value: V1.id } });
    fireEvent.change(select2, { target: { value: V2.id } });
    fireEvent.click(screen.getByTestId('dataset-version-compare-submit'));

    await waitFor(() =>
      expect(screen.getByTestId('dataset-version-diff-view')).toBeInTheDocument()
    );
    expect(screen.getByTestId('dataset-version-diff-summary')).toHaveTextContent('FIELD_ADDED');
    const added = screen.getByRole('region', { name: /Added fields/i });
    expect(added).toHaveTextContent('region');
  });
});
