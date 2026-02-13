/**
 * Retention Policy List Page Tests
 * Real useRetentionPolicies hook and real governanceRetentionService; only axios mocked (no mocks of application code).
 * Scenarios: loading, error, success (table), empty list.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { AxiosInstance } from 'axios';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { RetentionPolicy } from '../../../shared/types/governanceRetention';
import { RetentionAction, RetentionPolicyType } from '../../../shared/types/governanceRetention';
import { RetentionPolicyListPage } from './RetentionPolicyListPage';

vi.mock('axios', () => {
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
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

import { apiClient } from '../../../shared/api/client';

describe('RetentionPolicyListPage', () => {
  let queryClient: QueryClient;
  let mockAxiosInstance: AxiosInstance;

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    const realClient = apiClient.getClient();
    mockAxiosInstance = realClient;
    vi.mocked(mockAxiosInstance.get).mockClear();
  });

  it('should display loading state', async () => {
    let resolveList: (value: unknown) => void;
    const listPromise = new Promise((resolve) => {
      resolveList = resolve;
    });
    vi.mocked(mockAxiosInstance.get).mockReturnValue(listPromise as any);

    render(<RetentionPolicyListPage />, { wrapper });

    expect(screen.getByText(/loading retention policies/i)).toBeInTheDocument();

    resolveList!({
      data: {
        count: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
        next: null,
        previous: null,
        results: [],
      },
    });
    await waitFor(() => {
      expect(screen.queryByText(/loading retention policies/i)).not.toBeInTheDocument();
    });
  });

  it('should display error state', async () => {
    const err = {
      response: {
        status: 500,
        data: {
          error: {
            code: 'ERROR',
            message: 'Failed to load',
            http_status: 500,
            request_id: 'req-1',
            timestamp: new Date().toISOString(),
          },
        },
      },
    };
    vi.mocked(mockAxiosInstance.get).mockRejectedValue(err);

    render(<RetentionPolicyListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/failed to load retention policies/i)).toBeInTheDocument();
    });
  });

  it('should display retention policies table', async () => {
    const mockPolicies: RetentionPolicy[] = [
      {
        id: 'policy-1',
        tenant: 'tenant-1',
        name: 'Policy 1',
        description: 'Description 1',
        asset: 'asset-1',
        dataset: null,
        file: null,
        policy_type: RetentionPolicyType.TIME_BASED,
        retention_period_days: 30,
        event_trigger: null,
        action: RetentionAction.SOFT_DELETE,
        grace_period_days: 30,
        legal_hold: false,
        legal_hold_reason: null,
        legal_hold_expires_at: null,
        enabled: true,
        last_enforced_at: null,
        created_by: 'user-1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ];

    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: {
        count: 1,
        page: 1,
        page_size: 20,
        total_pages: 1,
        next: null,
        previous: null,
        results: mockPolicies,
      },
    } as any);

    render(<RetentionPolicyListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText('Policy 1')).toBeInTheDocument();
      expect(screen.getByText('TIME_BASED')).toBeInTheDocument();
    });

    const enabledBadges = screen.getAllByText('Enabled');
    const statusBadge = enabledBadges.find((el) =>
      el.classList.contains('governance-status-badge')
    );
    expect(statusBadge).toBeInTheDocument();
  });

  it('should display empty state when no policies', async () => {
    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: {
        count: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
        next: null,
        previous: null,
        results: [],
      },
    } as any);

    render(<RetentionPolicyListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /no retention policies/i })).toBeInTheDocument();
    });
  });
});
