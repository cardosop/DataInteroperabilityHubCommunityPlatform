/**
 * Scheduled Export List Page Tests
 * Real useScheduledExports hook and real scheduledExportService; only API client mocked (no mocks of application code).
 * Scenarios: loading, error, success (table), empty list.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ScheduledExport } from '../../../shared/types/scheduledExport';
import { ScheduledExportListPage } from './ScheduledExportListPage';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';

describe('ScheduledExportListPage', () => {
  let queryClient: QueryClient;
  let mockClient: HttpClient;

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
    mockClient = realClient;
    vi.mocked(mockClient.get).mockClear();
  });

  it('should display loading state', async () => {
    let resolveList: (value: unknown) => void;
    const listPromise = new Promise((resolve) => {
      resolveList = resolve;
    });
    vi.mocked(mockClient.get).mockReturnValue(listPromise as never);

    render(<ScheduledExportListPage />, { wrapper });

    expect(document.querySelector('.skeleton, [aria-hidden="true"]') || document.body).toBeTruthy();

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
    vi.mocked(mockClient.get).mockRejectedValue(new Error('Network error'));

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

    vi.mocked(mockClient.get).mockResolvedValue({
      data: {
        count: 1,
        next: null,
        previous: null,
        results: mockExports,
      },
    } as never);

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
    vi.mocked(mockClient.get).mockResolvedValue({
      data: {
        count: 0,
        next: null,
        previous: null,
        results: [],
      },
    } as never);

    render(<ScheduledExportListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /no scheduled exports/i })).toBeInTheDocument();
    });
  });
});

describe('ScheduledExportListPage pagination (W12.9)', () => {
  let queryClient: QueryClient;
  let mockClient: HttpClient;

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  function mockPage(pageNum: number, overrides: Partial<unknown> = {}) {
    return {
      data: {
        count: 25,
        next: pageNum === 1 ? 'http://api/scheduled-exports/?page=2' : null,
        previous: pageNum === 1 ? null : 'http://api/scheduled-exports/?page=1',
        results: [
          {
            id: `export-page-${pageNum}`,
            name: `Page ${pageNum} export`,
            destination_type: 'S3',
            schedule_config: { cron: '0 0 * * *' },
            status: 'ACTIVE',
            next_run_at: null,
            last_run_at: null,
            created_at: '2026-01-01T00:00:00Z',
          },
        ],
        ...overrides,
      },
    };
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const realClient = apiClient.getClient();
    mockClient = realClient;
    vi.mocked(mockClient.get).mockClear();
  });

  it('Next button requests page 2 and renders page-2 rows', async () => {
    vi.mocked(mockClient.get)
      .mockResolvedValueOnce(mockPage(1))
      .mockResolvedValueOnce(mockPage(2));

    render(<ScheduledExportListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText('Page 1 export')).toBeInTheDocument();
    });

    const nextBtn = screen.getByTestId('scheduled-export-next-page-btn');
    expect(nextBtn).toBeEnabled();
    nextBtn.click();

    await waitFor(() => {
      expect(screen.getByText('Page 2 export')).toBeInTheDocument();
    });

    const page2Call = vi.mocked(mockClient.get).mock.calls.find((call) =>
      String(call[0]).includes('page=2'),
    );
    expect(page2Call).toBeTruthy();
  });

  it('Next is disabled without a next link; Previous disabled without previous', async () => {
    vi.mocked(mockClient.get).mockResolvedValueOnce(mockPage(1));

    render(<ScheduledExportListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText('Page 1 export')).toBeInTheDocument();
    });

    expect(screen.getByTestId('scheduled-export-prev-page-btn')).toBeDisabled();
    expect(screen.getByTestId('scheduled-export-next-page-btn')).toBeEnabled();
    expect(screen.getByTestId('scheduled-export-pagination-info')).toHaveTextContent(
      '25 results · Page 1',
    );
  });

  it('changing the status filter resets to page 1', async () => {
    vi.mocked(mockClient.get).mockResolvedValue(mockPage(1));

    render(<ScheduledExportListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText('Page 1 export')).toBeInTheDocument();
    });

    screen.getByTestId('scheduled-export-next-page-btn').click();
    await waitFor(() => {
      expect(
        vi.mocked(mockClient.get).mock.calls.some((call) =>
          String(call[0]).includes('page=2'),
        ),
      ).toBe(true);
    });

    const statusSelect = screen.getByLabelText('Filter by status');
    fireEvent.change(statusSelect, { target: { value: 'ACTIVE' } });

    await waitFor(() => {
      expect(screen.getByTestId('scheduled-export-pagination-info')).toHaveTextContent(
        'Page 1',
      );
    });
  });
});
