/**
 * useDatasets — paginated-results normalization pin (Phase 1.5 follow-up).
 *
 * Representative of the 19-hook sweep: a 200 whose body is NOT the
 * paginated envelope (proxy error envelope, drift) must land as
 * ``{results: []}`` in the query data, so ``DatasetListPage``'s
 * ``!data || data.results.length === 0`` guard renders the empty state
 * instead of crashing at ``data.results.map``.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { datasetService } from '../services/datasetService';
import { useDatasets } from './useDatasets';

describe('useDatasets normalization', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  function renderDatasets() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    return renderHook(() => useDatasets(), { wrapper });
  }

  it('passes a well-formed envelope through', async () => {
    vi.spyOn(datasetService, 'list').mockResolvedValue({
      count: 1,
      page: 1,
      page_size: 50,
      total_pages: 1,
      has_next: false,
      has_previous: false,
      next_page: null,
      previous_page: null,
      results: [{ id: 'd1', name: 'Dataset One' }],
    } as never);

    const { result } = renderDatasets();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toEqual([{ id: 'd1', name: 'Dataset One' }]);
  });

  it('normalizes an error-envelope 200 to an empty results array', async () => {
    vi.spyOn(datasetService, 'list').mockResolvedValue({
      error: 'proxy exploded',
    } as never);

    const { result } = renderDatasets();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toEqual([]);
  });

  it('normalizes a non-array results key to []', async () => {
    vi.spyOn(datasetService, 'list').mockResolvedValue({
      count: 1,
      results: { d1: true },
    } as never);

    const { result } = renderDatasets();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toEqual([]);
  });
});
