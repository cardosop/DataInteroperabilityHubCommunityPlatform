/**
 * RatingsTab Tests
 * Verifies assetId-only mode (no asset selector when assetId provided and assetIdOnly=true).
 * Mocks only axios (network layer).
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { AxiosInstance } from 'axios';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { RatingsTab } from './RatingsTab';
import { apiClient } from '../../../shared/api/client';

vi.mock('axios', () => {
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  } as unknown as AxiosInstance;

  return {
    default: {
      create: vi.fn(() => mockAxiosInstance),
    },
  };
});

describe('RatingsTab', () => {
  let queryClient: QueryClient;
  let mockAxiosInstance: AxiosInstance;

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
    mockAxiosInstance = apiClient.getClient();
    vi.mocked(mockAxiosInstance.get).mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('social') && url.includes('ratings')) {
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
      <RatingsTab assetId="asset-123" assetIdOnly />,
      { wrapper }
    );

    await waitFor(() => {
      expect(screen.queryByText(/loading ratings/i)).not.toBeInTheDocument();
    });

    expect(screen.queryByLabelText(/select asset/i)).not.toBeInTheDocument();
  });

  it('shows asset selector when assetIdOnly is false', async () => {
    render(
      <RatingsTab assetId={null} assetIdOnly={false} />,
      { wrapper }
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/select asset/i)).toBeInTheDocument();
    });
  });
});
