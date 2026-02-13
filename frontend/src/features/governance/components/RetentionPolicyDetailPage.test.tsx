/**
 * Retention Policy Detail Page Tests
 * Real useRetentionPolicy and useDeleteRetentionPolicy; only axios mocked (no mocks of application code).
 * Scenarios: loading, error, success (detail content).
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { AxiosInstance } from 'axios';
import { type ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { RetentionPolicy } from '../../../shared/types/governanceRetention';
import { RetentionAction, RetentionPolicyType } from '../../../shared/types/governanceRetention';
import { RetentionPolicyDetailPage } from './RetentionPolicyDetailPage';

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

describe('RetentionPolicyDetailPage', () => {
  let queryClient: QueryClient;
  let mockAxiosInstance: AxiosInstance;

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/governance/retention/policy-1']}>
          <Routes>
            <Route path="/governance/retention/:id" element={children} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    const realClient = apiClient.getClient();
    mockAxiosInstance = realClient;
    vi.mocked(mockAxiosInstance.get).mockClear();
    vi.mocked(mockAxiosInstance.delete).mockClear();
  });

  it('should display loading state', async () => {
    let resolveGet: (value: unknown) => void;
    const getPromise = new Promise((resolve) => {
      resolveGet = resolve;
    });
    vi.mocked(mockAxiosInstance.get).mockReturnValue(getPromise as any);

    render(<RetentionPolicyDetailPage />, { wrapper });

    expect(screen.getByText(/loading retention policy/i)).toBeInTheDocument();

    resolveGet!({
      data: {
        id: 'policy-1',
        tenant: 'tenant-1',
        name: 'Test Policy',
        description: 'Test description',
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
      } as RetentionPolicy,
    });
    await waitFor(() => {
      expect(screen.queryByText(/loading retention policy/i)).not.toBeInTheDocument();
    });
  });

  it('should display error state', async () => {
    const err = {
      response: {
        status: 404,
        data: {
          error: {
            code: 'NOT_FOUND',
            message: 'Policy not found',
            http_status: 404,
            request_id: 'req-1',
            timestamp: new Date().toISOString(),
          },
        },
      },
    };
    vi.mocked(mockAxiosInstance.get).mockRejectedValue(err);

    render(<RetentionPolicyDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/failed to load retention policy/i)).toBeInTheDocument();
    });
  });

  it('should display retention policy details', async () => {
    const mockPolicy: RetentionPolicy = {
      id: 'policy-1',
      tenant: 'tenant-1',
      name: 'Test Policy',
      description: 'Test description',
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
    };

    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: mockPolicy,
    } as any);

    render(<RetentionPolicyDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText('Test Policy')).toBeInTheDocument();
      expect(screen.getByText('Test description')).toBeInTheDocument();
      expect(screen.getByText('TIME_BASED')).toBeInTheDocument();
    });

    const daysElements = screen.getAllByText('30 days');
    expect(daysElements.length).toBeGreaterThan(0);
  });
});
