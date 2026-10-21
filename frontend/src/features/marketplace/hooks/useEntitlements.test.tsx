/**
 * Phase 85.11 — useEntitlements hook tests.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/entitlementService', () => ({
  entitlementService: {
    list: vi.fn(),
    getById: vi.fn(),
    checkAccess: vi.fn(),
    revoke: vi.fn(),
  },
}));

vi.mock('../../../shared/components/Toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
  ToastProvider: ({ children }: { children: ReactNode }) => children,
}));

import { entitlementService } from '../services/entitlementService';
import { useEntitlements, useEntitlement } from './useEntitlements';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe('useEntitlements', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches entitlements', async () => {
    vi.mocked(entitlementService.list).mockResolvedValue({ results: [{ id: 'e1' }], count: 1 });
    const { result } = renderHook(() => useEntitlements(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toHaveLength(1);
  });

  it('passes filters', async () => {
    vi.mocked(entitlementService.list).mockResolvedValue({ results: [], count: 0 });
    renderHook(() => useEntitlements({ status: 'ACTIVE' }), { wrapper: createWrapper() });
    await waitFor(() => expect(entitlementService.list).toHaveBeenCalledWith({ status: 'ACTIVE' }));
  });

  it('handles error', async () => {
    vi.mocked(entitlementService.list).mockRejectedValue(new Error('fail'));
    const { result } = renderHook(() => useEntitlements(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it('useEntitlement disabled when id null', () => {
    const { result } = renderHook(() => useEntitlement(null), { wrapper: createWrapper() });
    expect(result.current.fetchStatus).toBe('idle');
  });

  it('useEntitlement fetches by id', async () => {
    vi.mocked(entitlementService.getById).mockResolvedValue({ id: 'e1', status: 'ACTIVE' });
    const { result } = renderHook(() => useEntitlement('e1'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe('e1');
  });
});
