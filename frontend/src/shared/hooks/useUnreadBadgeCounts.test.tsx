/**
 * useUnreadBadgeCounts tests.
 *
 * Verifies that:
 *   - Non-admin users never trigger the admin-only pending-count request.
 *   - TENANT_ADMIN users surface the server-returned count.
 *   - PLATFORM_ADMIN users (is_platform_admin flag) surface the count.
 *   - Missing/unauthenticated users default to zero and do not fetch.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/client');

import { apiClient } from '../api/client';
import { useAuthStore } from '../../features/auth/store/authStore';
import { useUnreadBadgeCounts } from './useUnreadBadgeCounts';

function makeWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function setUser(partial: Partial<{
  roles: string[];
  is_platform_admin: boolean;
  id: string;
}>) {
  useAuthStore.setState({
    user: {
      id: partial.id ?? 'user-1',
      email: 'user@example.com',
      name: 'User',
      roles: partial.roles ?? [],
      tenant_id: 'tenant-1',
      is_active: true,
      is_platform_admin: partial.is_platform_admin,
    },
    active_tenant_id: null,
    isAuthenticated: true,
    isLoading: false,
    error: null,
  });
}

describe('useUnreadBadgeCounts', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  afterEach(() => {
    useAuthStore.setState({
      user: null,
      active_tenant_id: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
  });

  it('returns zero and does not fetch for non-admin users', async () => {
    setUser({ roles: ['DATA_CONSUMER'] });
    const mock = apiClient.getClient();
    const getMock = vi.mocked(mock.get);
    getMock.mockResolvedValue({ data: { count: 99 } } as never);

    const { result } = renderHook(() => useUnreadBadgeCounts(), {
      wrapper: makeWrapper(queryClient),
    });

    // Give React Query a chance to schedule the query
    await new Promise((r) => setTimeout(r, 10));

    expect(result.current.governancePending).toBe(0);
    expect(getMock).not.toHaveBeenCalled();
  });

  it('fetches and returns count for TENANT_ADMIN', async () => {
    setUser({ roles: ['TENANT_ADMIN'] });
    const mock = apiClient.getClient();
    const getMock = vi.mocked(mock.get);
    getMock.mockResolvedValue({ data: { count: 5 } } as never);

    const { result } = renderHook(() => useUnreadBadgeCounts(), {
      wrapper: makeWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.governancePending).toBe(5);
    });

    expect(getMock).toHaveBeenCalledWith(
      'governance/access-requests/pending-count/',
    );
  });

  it('fetches for platform admins via is_platform_admin flag', async () => {
    setUser({ roles: [], is_platform_admin: true });
    const mock = apiClient.getClient();
    const getMock = vi.mocked(mock.get);
    getMock.mockResolvedValue({ data: { count: 2 } } as never);

    const { result } = renderHook(() => useUnreadBadgeCounts(), {
      wrapper: makeWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.governancePending).toBe(2);
    });

    expect(getMock).toHaveBeenCalledTimes(1);
  });

  it('returns zero when user is null', async () => {
    useAuthStore.setState({
      user: null,
      active_tenant_id: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
    const mock = apiClient.getClient();
    const getMock = vi.mocked(mock.get);

    const { result } = renderHook(() => useUnreadBadgeCounts(), {
      wrapper: makeWrapper(queryClient),
    });

    await new Promise((r) => setTimeout(r, 10));

    expect(result.current.governancePending).toBe(0);
    expect(getMock).not.toHaveBeenCalled();
  });
});
