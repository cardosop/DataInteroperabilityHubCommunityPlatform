/**
 * Scheduled Export List Page Tests
 * Real useScheduledExports hook and real scheduledExportService; only axios mocked (no mocks of application code).
 * Scenarios: loading, error, success (table), empty list.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { AxiosInstance } from 'axios';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ScheduledExport } from '../../../shared/types/scheduledExport';
import { ScheduledExportListPage } from './ScheduledExportListPage';

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

describe('ScheduledExportListPage', () => {
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

    render(<ScheduledExportListPage />, { wrapper });

    expect(screen.getByText(/loading scheduled exports/i)).toBeInTheDocument();

    resolveList!({
      data: {
        count: 0,
        next: null,
        previous: null,
        results: [],
      },
    });
    await waitFor(() => {
      expect(screen.queryByText(/loading scheduled exports/i)).not.toBeInTheDocument();
    });
  });

  it('should display error state', async () => {
    vi.mocked(mockAxiosInstance.get).mockRejectedValue(new Error('Network error'));

    render(<ScheduledExportListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/failed to load scheduled exports/i)).toBeInTheDocument();
    });
  });

  it('should display scheduled exports table', async () => {
    const mockExports: ScheduledExport[] = [
      {
        id: 'export-1',
        tenant: 'tenant-1',
        tenant_name: 'Test Tenant',
        name: 'Daily Export',
        schedule_config: { cron: '0 2 * * *' },
        destination_type: 'S3',
        destination_config: { bucket: 'my-bucket' },
        source_scope: { asset_ids: ['asset-1'] },
        status: 'ACTIVE',
        next_run_at: '2024-01-02T02:00:00Z',
        last_run_at: null,
        last_run_status: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ];

    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: {
        count: 1,
        next: null,
        previous: null,
        results: mockExports,
      },
    } as any);

    render(<ScheduledExportListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText('Daily Export')).toBeInTheDocument();
      expect(screen.getByText('S3')).toBeInTheDocument();
      expect(screen.getByText('ACTIVE')).toBeInTheDocument();
      expect(screen.getByText('0 2 * * *')).toBeInTheDocument();
    });

    expect(screen.getByTestId('scheduled-export-list-page')).toBeInTheDocument();
  });

  it('should display empty state when no scheduled exports', async () => {
    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: {
        count: 0,
        next: null,
        previous: null,
        results: [],
      },
    } as any);

    render(<ScheduledExportListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /no scheduled exports/i })).toBeInTheDocument();
    });
  });
});
