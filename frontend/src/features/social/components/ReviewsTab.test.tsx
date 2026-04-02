/**
 * ReviewsTab Tests
 * Verifies assetId-only mode (no asset selector when assetId provided and assetIdOnly=true).
 * Mocks only API client (network layer).
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { HttpClient } from '../../../shared/types/api';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ReviewsTab } from './ReviewsTab';
import { apiClient } from '../../../shared/api/client';

vi.mock('../../../shared/api/client');

describe('ReviewsTab', () => {
  let queryClient: QueryClient;
  let mockClient: HttpClient;

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    mockClient = apiClient.getClient();
    vi.mocked(mockClient.get).mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('social') && url.includes('reviews')) {
        return Promise.resolve({ data: { results: [], count: 0 } });
      }
      if (typeof url === 'string' && url.includes('assets')) {
        return Promise.resolve({ data: { results: [], count: 0 } });
      }
      return Promise.reject(new Error(`Unmocked: ${url}`));
    });
  });

  it('hides asset selector when assetIdOnly is true', async () => {
    render(
      <ReviewsTab assetId="asset-123" assetIdOnly />,
      { wrapper }
    );

    await waitFor(() => {
      expect(screen.queryByText(/loading reviews/i)).not.toBeInTheDocument();
    });

    expect(screen.queryByLabelText(/select asset/i)).not.toBeInTheDocument();
  });

  it('shows status filter when assetIdOnly is true', async () => {
    render(
      <ReviewsTab assetId="asset-123" assetIdOnly />,
      { wrapper }
    );

    await waitFor(() => {
      expect(screen.queryByText(/loading reviews/i)).not.toBeInTheDocument();
    });

    expect(screen.getByLabelText(/status/i)).toBeInTheDocument();
  });

  it('shows asset selector when assetIdOnly is false', async () => {
    render(
      <ReviewsTab assetId={null} assetIdOnly={false} />,
      { wrapper }
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/select asset/i)).toBeInTheDocument();
    });
  });
});
