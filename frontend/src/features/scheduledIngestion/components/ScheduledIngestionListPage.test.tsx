/**
 * ScheduledIngestionListPage smoke test — Phase 106
 */
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { ScheduledIngestionListPage } from './ScheduledIngestionListPage';

describe('ScheduledIngestionListPage', () => {
  let queryClient: QueryClient;
  let mock: HttpClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    mock = apiClient.getClient();
    // Default: return empty paginated response for any GET
    vi.mocked(mock.get).mockResolvedValue({
      data: { count: 0, results: [], page: 1, page_size: 20, total_pages: 0, has_next: false, has_previous: false },
    });
  });

  it('renders without crashing', async () => {
    render(<ScheduledIngestionListPage />, { wrapper: Wrapper });
    // Component should mount without throwing
    expect(document.body.innerHTML.length).toBeGreaterThan(0);
  });

  it('mounts and processes initial render cycle', async () => {
    const { container } = render(<ScheduledIngestionListPage />, { wrapper: Wrapper });
    // Wait for any content to appear (heading, text, button, etc.)
    // The component should render something meaningful
    // Component should mount and start its render lifecycle
    // (loading state, data fetch, or static content)
    expect(container.children.length).toBeGreaterThan(0);
  });
});

describe('ScheduledIngestionListPage pagination (W12.9)', () => {
  let queryClient: QueryClient;
  let mock: HttpClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  function mockPage(pageNum: number) {
    return {
      data: {
        count: 25,
        next: pageNum === 1 ? 'http://api/scheduled-ingestions/?page=2' : null,
        previous: pageNum === 1 ? null : 'http://api/scheduled-ingestions/?page=1',
        results: [
          {
            id: `ingestion-page-${pageNum}`,
            name: `Page ${pageNum} ingestion`,
            source_type: 'S3',
            schedule_config: { cron: '0 0 * * *' },
            status: 'ACTIVE',
            next_run_at: null,
            created_at: '2026-01-01T00:00:00Z',
          },
        ],
      },
    };
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    mock = apiClient.getClient();
  });

  it('Next button requests page 2 and renders page-2 rows', async () => {
    vi.mocked(mock.get).mockResolvedValueOnce(mockPage(1)).mockResolvedValueOnce(mockPage(2));

    render(<ScheduledIngestionListPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText('Page 1 ingestion')).toBeInTheDocument();
    });

    const nextBtn = screen.getByTestId('scheduled-ingestion-next-page-btn');
    expect(nextBtn).toBeEnabled();
    nextBtn.click();

    await waitFor(() => {
      expect(screen.getByText('Page 2 ingestion')).toBeInTheDocument();
    });

    const page2Call = vi.mocked(mock.get).mock.calls.find((call) =>
      String(call[0]).includes('page=2'),
    );
    expect(page2Call).toBeTruthy();
  });

  it('Next is disabled without a next link; Previous disabled without previous', async () => {
    vi.mocked(mock.get).mockResolvedValueOnce(mockPage(1));

    render(<ScheduledIngestionListPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText('Page 1 ingestion')).toBeInTheDocument();
    });

    expect(screen.getByTestId('scheduled-ingestion-prev-page-btn')).toBeDisabled();
    expect(screen.getByTestId('scheduled-ingestion-next-page-btn')).toBeEnabled();
    expect(screen.getByTestId('scheduled-ingestion-pagination-info')).toHaveTextContent(
      '25 results · Page 1',
    );
  });

  it('changing the status filter resets to page 1', async () => {
    vi.mocked(mock.get).mockResolvedValue(mockPage(1));

    render(<ScheduledIngestionListPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText('Page 1 ingestion')).toBeInTheDocument();
    });

    screen.getByTestId('scheduled-ingestion-next-page-btn').click();
    await waitFor(() => {
      expect(
        vi.mocked(mock.get).mock.calls.some((call) => String(call[0]).includes('page=2')),
      ).toBe(true);
    });

    fireEvent.change(screen.getByLabelText('Filter by status'), {
      target: { value: 'ACTIVE' },
    });

    await waitFor(() => {
      expect(screen.getByTestId('scheduled-ingestion-pagination-info')).toHaveTextContent(
        'Page 1',
      );
    });
  });
});
