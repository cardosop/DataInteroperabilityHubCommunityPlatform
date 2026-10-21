/**
 * useContractLineageVisualization — point-in-time cache semantics (b7).
 *
 * Pins the regression behind the lineage-time-travel "reset" leg: with
 * the app's default 5-min staleTime, returning the query key to its
 * initial (no-as_of) shape re-subscribed to a query whose data was
 * seconds old, so React Query skipped the refetch and the graph kept
 * the anchor-time snapshot — the E2E reset waiter never saw the
 * no-as_of request. The hook must declare staleTime: 0 so every
 * (re)subscribe refetches the live view.
 */
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi, type ReactNode } from 'vitest';

vi.mock('../services/contractService', () => ({
  contractService: {
    getLineageVisualization: vi.fn(),
  },
}));

import { contractService } from '../services/contractService';
import { useContractLineageVisualization } from './useContracts';

const getLineageVisualization = vi.mocked(contractService.getLineageVisualization);

function makeWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('useContractLineageVisualization cache semantics', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('refetches the live view when the key returns to its initial shape (reset)', async () => {
    getLineageVisualization.mockResolvedValue({
      nodes: [],
      links: [],
    } as never);

    // App defaults (queryClient.ts): staleTime 5 min — the exact
    // regression condition the hook's staleTime: 0 overrides.
    const qc = new QueryClient({
      defaultOptions: { queries: { staleTime: 5 * 60 * 1000, retry: false } },
    });

    const { rerender } = renderHook(
      ({ asOf }: { asOf: string | null }) =>
        useContractLineageVisualization('c1', {
          format: 'json',
          max_depth: 10,
          ...(asOf ? { as_of: asOf } : {}),
        }),
      { wrapper: makeWrapper(qc), initialProps: { asOf: null } },
    );

    // Initial live fetch.
    await waitFor(() => expect(getLineageVisualization).toHaveBeenCalledTimes(1));

    // Apply an anchor — new key shape → fetch.
    rerender({ asOf: '2026-01-01T00:00:00.000Z' });
    await waitFor(() => expect(getLineageVisualization).toHaveBeenCalledTimes(2));

    // Reset — key returns to the initial shape. The cached initial
    // data is ~0s old, so under the app default staleTime React Query
    // serves the cache and NEVER refetches; staleTime: 0 must force
    // the third (live) request.
    rerender({ asOf: null });
    await waitFor(() => expect(getLineageVisualization).toHaveBeenCalledTimes(3));

    const lastCallParams = getLineageVisualization.mock.calls[2][1] as {
      as_of?: string;
    };
    expect(lastCallParams.as_of).toBeUndefined();
  });
});
