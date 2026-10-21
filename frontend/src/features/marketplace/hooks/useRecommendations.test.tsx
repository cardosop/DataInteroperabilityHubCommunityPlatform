/**
 * W5.4 (MEDIUM-8) — recommendation-feedback submission failures were
 * silent (plain useMutation, no onError). The pin asserts the real
 * error-toast surface; only the recommendationsService HTTP seam is
 * stubbed.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/recommendationsService');

import { recommendationsService } from '../services/recommendationsService';
import { ToastProvider } from '../../../shared/components/Toast';
import { useSubmitRecommendationFeedback } from './useRecommendations';

function wrap(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <ToastProvider>{children}</ToastProvider>
      </QueryClientProvider>
    );
  };
}

describe('useSubmitRecommendationFeedback surfaces failures (MEDIUM-8)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
  });

  it('fires an error toast when feedback submission fails', async () => {
    vi.mocked(recommendationsService.submitFeedback).mockRejectedValue(
      new Error('feedback rejected'),
    );

    const { result } = renderHook(() => useSubmitRecommendationFeedback(), {
      wrapper: wrap(queryClient),
    });

    act(() => {
      result.current.mutate({ listingId: 'l1', helpful: true });
    });

    await waitFor(() => {
      const toast = screen.getByTestId('toast');
      expect(toast).toHaveClass('toast-error');
      expect(toast).toHaveTextContent(/feedback rejected/i);
    });
  });
});
