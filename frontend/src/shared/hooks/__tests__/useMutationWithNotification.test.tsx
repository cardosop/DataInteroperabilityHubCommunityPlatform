/**
 * useMutationWithNotification Tests — Phase 41
 */

import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { useMutationWithNotification } from '../useMutationWithNotification';

// Mock the Toast module
const mockSuccess = vi.fn();
const mockError = vi.fn();
vi.mock('../../components/Toast', () => ({
  useToast: () => ({ success: mockSuccess, error: mockError, info: vi.fn() }),
  ToastProvider: ({ children }: { children: ReactNode }) => children,
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('useMutationWithNotification', () => {
  it('calls toast.success with the provided successMessage on success', async () => {
    mockSuccess.mockClear();
    const { result } = renderHook(
      () =>
        useMutationWithNotification({
          mutationFn: async () => 'ok',
          successMessage: 'Item created',
        }),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      await result.current.mutateAsync(undefined);
    });

    expect(mockSuccess).toHaveBeenCalledWith('Item created');
  });

  it('calls toast.error with the provided errorMessage on failure', async () => {
    mockError.mockClear();
    const { result } = renderHook(
      () =>
        useMutationWithNotification({
          mutationFn: async () => { throw new Error('server error'); },
          errorMessage: 'Failed to create item',
        }),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      try {
        await result.current.mutateAsync(undefined);
      } catch {
        // expected
      }
    });

    expect(mockError).toHaveBeenCalledWith('Failed to create item');
  });

  it('falls back to err.message when errorMessage is not provided', async () => {
    mockError.mockClear();
    const { result } = renderHook(
      () =>
        useMutationWithNotification({
          mutationFn: async () => { throw new Error('Something broke'); },
        }),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      try {
        await result.current.mutateAsync(undefined);
      } catch {
        // expected
      }
    });

    expect(mockError).toHaveBeenCalledWith('Something broke');
  });

  it('runs custom onSuccess callback alongside toast', async () => {
    mockSuccess.mockClear();
    const customOnSuccess = vi.fn();
    const { result } = renderHook(
      () =>
        useMutationWithNotification({
          mutationFn: async () => 'data',
          successMessage: 'Done',
          onSuccess: customOnSuccess,
        }),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      await result.current.mutateAsync(undefined);
    });

    expect(mockSuccess).toHaveBeenCalledWith('Done');
    expect(customOnSuccess).toHaveBeenCalled();
  });

  it('supports function-based successMessage', async () => {
    mockSuccess.mockClear();
    const { result } = renderHook(
      () =>
        useMutationWithNotification({
          mutationFn: async (name: string) => ({ name }),
          successMessage: (data) => `Created ${data.name}`,
        }),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      await result.current.mutateAsync('Widget');
    });

    expect(mockSuccess).toHaveBeenCalledWith('Created Widget');
  });
});
