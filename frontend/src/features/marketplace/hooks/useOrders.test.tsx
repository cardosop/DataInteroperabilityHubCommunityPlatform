/**
 * Phase 85.10 — useOrders hook tests.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/orderService', () => ({
  orderService: {
    list: vi.fn(),
    getById: vi.fn(),
    create: vi.fn(),
    purchase: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
  },
}));

vi.mock('../../../shared/components/Toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
  ToastProvider: ({ children }: { children: ReactNode }) => children,
}));

import { orderService } from '../services/orderService';
import { useOrders, useOrder } from './useOrders';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe('useOrders', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches orders list', async () => {
    vi.mocked(orderService.list).mockResolvedValue({ results: [{ id: 'o1' }], count: 1 });
    const { result } = renderHook(() => useOrders(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toHaveLength(1);
  });

  it('passes filters', async () => {
    vi.mocked(orderService.list).mockResolvedValue({ results: [], count: 0 });
    renderHook(() => useOrders({ status: 'APPROVED' }), { wrapper: createWrapper() });
    await waitFor(() => expect(orderService.list).toHaveBeenCalledWith({ status: 'APPROVED' }));
  });

  it('handles error', async () => {
    vi.mocked(orderService.list).mockRejectedValue(new Error('fail'));
    const { result } = renderHook(() => useOrders(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it('useOrder disabled when id null', () => {
    const { result } = renderHook(() => useOrder(null), { wrapper: createWrapper() });
    expect(result.current.fetchStatus).toBe('idle');
  });

  it('useOrder fetches by id', async () => {
    vi.mocked(orderService.getById).mockResolvedValue({ id: 'o1', status: 'PENDING' });
    const { result } = renderHook(() => useOrder('o1'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe('o1');
  });
});
