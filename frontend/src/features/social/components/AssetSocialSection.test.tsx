/**
 * AssetSocialSection Tests
 * Verifies capability-gating and tab rendering. Mocks useCapabilities to control
 * capability availability; uses real tab components with axios mocked for their API calls.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import type { AxiosInstance } from 'axios';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AssetSocialSection } from './AssetSocialSection';
import { apiClient } from '../../../shared/api/client';

const mockIsCapabilityAvailable = vi.fn();

vi.mock('../../../shared/hooks/useCapabilities', () => ({
  useCapabilities: () => ({
    isCapabilityAvailable: mockIsCapabilityAvailable,
    capabilities: {},
    isLoading: false,
    getCapability: () => null,
  }),
}));

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

describe('AssetSocialSection', () => {
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
      if (typeof url === 'string' && (url.includes('social') && url.includes('ratings'))) {
        return Promise.resolve({ data: { results: [], count: 0 } });
      }
      if (typeof url === 'string' && (url.includes('social') && url.includes('reviews'))) {
        return Promise.resolve({ data: { results: [], count: 0 } });
      }
      if (typeof url === 'string' && (url.includes('social') && url.includes('comments'))) {
        return Promise.resolve({ data: { results: [], count: 0 } });
      }
      if (typeof url === 'string' && url.includes('assets')) {
        return Promise.resolve({ data: { results: [], count: 0 } });
      }
      return Promise.reject(new Error(`Unmocked URL: ${url}`));
    });
  });

  it('renders nothing when no social capabilities available', () => {
    mockIsCapabilityAvailable.mockReturnValue(false);

    const { container } = render(
      <AssetSocialSection assetId="asset-123" />,
      { wrapper }
    );

    expect(container.querySelector('[data-testid="asset-social-section"]')).toBeNull();
  });

  it('renders Community section with tabs when social capabilities available', () => {
    mockIsCapabilityAvailable.mockImplementation((key: string) =>
      ['social.ratings', 'social.reviews', 'social.comments'].includes(key)
    );

    render(<AssetSocialSection assetId="asset-123" />, { wrapper });

    expect(screen.getByTestId('asset-social-section')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /community/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /ratings/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reviews/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /comments/i })).toBeInTheDocument();
  });

  it('shows Ratings tab active by default when ratings capability available', () => {
    mockIsCapabilityAvailable.mockImplementation((key: string) =>
      ['social.ratings', 'social.reviews', 'social.comments'].includes(key)
    );

    render(<AssetSocialSection assetId="asset-123" />, { wrapper });

    const ratingsTab = screen.getByRole('button', { name: /ratings/i });
    expect(ratingsTab).toHaveClass('active');
  });

  it('asset selector is hidden when embedded (assetIdOnly)', () => {
    mockIsCapabilityAvailable.mockImplementation((key: string) =>
      ['social.ratings', 'social.reviews', 'social.comments'].includes(key)
    );

    render(<AssetSocialSection assetId="asset-123" />, { wrapper });

    expect(screen.queryByLabelText(/select asset/i)).not.toBeInTheDocument();
  });

  it('defaults to first available tab when ratings not available', () => {
    mockIsCapabilityAvailable.mockImplementation((key: string) =>
      key === 'social.reviews' || key === 'social.comments'
    );

    render(<AssetSocialSection assetId="asset-123" />, { wrapper });

    const reviewsTab = screen.getByRole('button', { name: /reviews/i });
    const commentsTab = screen.getByRole('button', { name: /comments/i });
    expect(reviewsTab).toHaveClass('active');
    expect(commentsTab).not.toHaveClass('active');
  });
});
