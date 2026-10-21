/**
 * ContractUsedByAssets — 223.2.2 tests.
 * Real useAssets + React Query; apiClient HTTP seam mocked.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { ContractUsedByAssets } from './ContractUsedByAssets';

function wrap(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

describe('ContractUsedByAssets', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  it('queries the asset list with contract_id and renders rows', async () => {
    const getMock = vi.mocked(apiClient.getClient().get);
    getMock.mockResolvedValue({
      data: {
        count: 2,
        page: 1,
        page_size: 20,
        total_pages: 1,
        next: null,
        previous: null,
        results: [
          { id: 'a-1', key: 'alpha', name: 'Alpha Asset', status: 'ACTIVE' },
          { id: 'a-2', key: 'beta', name: 'Beta Asset', status: 'DRAFT' },
        ],
      },
    } as never);

    render(<ContractUsedByAssets contractId="c-123" />, {
      wrapper: wrap(queryClient),
    });

    await waitFor(() => {
      expect(screen.getByTestId('used-by-asset-a-1')).toBeInTheDocument();
    });
    expect(screen.getByText(/Used by Assets \(2\)/)).toBeInTheDocument();
    expect(screen.getByText('Alpha Asset')).toBeInTheDocument();
    expect(screen.getByText('Beta Asset')).toBeInTheDocument();

    // Verify the request used the contract_id query param.
    const url = getMock.mock.calls[0][0] as string;
    expect(url).toContain('contract_id=c-123');
  });

  it('shows empty state when no assets use the contract', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: {
        count: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
        next: null,
        previous: null,
        results: [],
      },
    } as never);

    render(<ContractUsedByAssets contractId="c-orphan" />, {
      wrapper: wrap(queryClient),
    });

    await waitFor(() => {
      expect(
        screen.getByText(/no assets are currently using this contract/i),
      ).toBeInTheDocument();
    });
  });
});
