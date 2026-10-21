/**
 * W5.4 (MEDIUM-8) — lineage-subscription save failures were silent:
 * create/update/delete mutations had no onError surface, so a failed
 * save left the user with zero feedback. These pins assert the real
 * toast surface for each mutation. The apiClient HTTP seam is the only
 * stub; the hooks, QueryClient, and ToastProvider are real.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor, screen, act } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { ToastProvider } from '../../../shared/components/Toast';
import {
  useCreateLineageSubscription,
  useDeleteLineageSubscription,
  useUpdateLineageSubscription,
} from './useLineageSubscriptions';

function wrap(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <ToastProvider>{children}</ToastProvider>
      </QueryClientProvider>
    );
  };
}

describe('lineage subscription mutations surface failures (MEDIUM-8)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
  });

  it('surfaces a failed CREATE with an error toast', async () => {
    vi.mocked(apiClient.getClient().post).mockRejectedValue(new Error('subscription rejected'));

    const { result } = renderHook(() => useCreateLineageSubscription(), {
      wrapper: wrap(queryClient),
    });

    act(() => {
      result.current.mutate({ source_contract: 'c1', severity_threshold: 'HIGH' });
    });

    await waitFor(() => {
      const toast = screen.getByTestId('toast');
      expect(toast).toHaveClass('toast-error');
    });
  });

  it('surfaces a failed UPDATE with an error toast', async () => {
    vi.mocked(apiClient.getClient().patch).mockRejectedValue(new Error('update rejected'));

    const { result } = renderHook(() => useUpdateLineageSubscription(), {
      wrapper: wrap(queryClient),
    });

    act(() => {
      result.current.mutate({ id: 'sub-1', input: { in_app: false } });
    });

    await waitFor(() => {
      const toast = screen.getByTestId('toast');
      expect(toast).toHaveClass('toast-error');
      expect(toast).toHaveTextContent(/update rejected/i);
    });
  });

  it('surfaces a failed DELETE with an error toast', async () => {
    vi.mocked(apiClient.getClient().delete).mockRejectedValue(new Error('delete rejected'));

    const { result } = renderHook(() => useDeleteLineageSubscription(), {
      wrapper: wrap(queryClient),
    });

    act(() => {
      result.current.mutate('sub-1');
    });

    await waitFor(() => {
      const toast = screen.getByTestId('toast');
      expect(toast).toHaveClass('toast-error');
      expect(toast).toHaveTextContent(/delete rejected/i);
    });
  });
});
