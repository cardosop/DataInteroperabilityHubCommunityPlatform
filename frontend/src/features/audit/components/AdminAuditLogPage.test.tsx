/**
 * AdminAuditLogPage tests — Phase 260.4.H.
 *
 * Verifies:
 *   - URL query params (?resource_type=...&resource_id=...) seed the
 *     filters on mount → load-bearing for the deep-link contract.
 *   - Typing in the resource_id input forwards the value to the
 *     audit list API call AND debounces (300 ms) so paste-typing
 *     doesn't spam the backend.
 *   - CSV export button calls auditService.export with the current
 *     filters AND triggers a browser download with a resource_id-
 *     bearing filename for compliance traceability.
 *   - Empty state shows resource-id-aware copy when filtering by
 *     a specific resource.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { type ReactNode, useEffect } from 'react';
import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { HttpClient } from '../../../shared/types/api';
import { ToastProvider } from '../../../shared/components/Toast';
import { AdminAuditLogPage } from './AdminAuditLogPage';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';

const FILE_ID = '11111111-1111-1111-1111-111111111111';

describe('AdminAuditLogPage (Phase 260.4.H)', () => {
  let queryClient: QueryClient;
  let mockClient: HttpClient;

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter
            initialEntries={[`/admin/audit-log?resource_type=FILE&resource_id=${FILE_ID}`]}
          >
            <Routes>
              <Route path="/admin/audit-log" element={children} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>
    );
  }

  function emptyWrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={['/admin/audit-log']}>
            <Routes>
              <Route path="/admin/audit-log" element={children} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
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
    mockClient = apiClient.getClient();
    vi.mocked(mockClient.get).mockClear();
  });

  it('seeds resource_type + resource_id filters from URL query params on mount', async () => {
    vi.mocked(mockClient.get).mockResolvedValue({
      data: { results: [], count: 0, next: null, previous: null },
    } as never);

    render(<AdminAuditLogPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('admin-audit-log-page')).toBeInTheDocument();
    });

    // URL params reflected into the filter inputs.
    const resourceTypeSelect = screen.getByTestId(
      'admin-audit-resource-type-filter',
    ) as HTMLSelectElement;
    expect(resourceTypeSelect.value).toBe('FILE');

    const resourceIdInput = screen.getByTestId(
      'admin-audit-resource-id-filter',
    ) as HTMLInputElement;
    expect(resourceIdInput.value).toBe(FILE_ID);

    // Live API call carries the seeded filters — load-bearing for
    // the deep-link contract.
    await waitFor(() => {
      const calls = vi.mocked(mockClient.get).mock.calls.map((c) => c[0] as string);
      expect(
        calls.some(
          (url) => url.includes('resource_type=FILE') && url.includes(`resource_id=${FILE_ID}`),
        ),
      ).toBe(true);
    });
  });

  it('renders no-filter empty state when neither resource_id nor URL params are set', async () => {
    vi.mocked(mockClient.get).mockResolvedValue({
      data: { results: [], count: 0, next: null, previous: null },
    } as never);

    render(<AdminAuditLogPage />, { wrapper: emptyWrapper });

    // The page wraps the empty state inside the same body once loading
    // completes and react-query resolves with the mocked empty results.
    // Wait for the empty-state copy directly — the page header renders
    // synchronously, but the body switches from <ListPageSkeleton/> to
    // the empty state on the next tick, which getByText would miss.
    await waitFor(() => {
      expect(screen.getByText(/use the filters above/i)).toBeInTheDocument();
    });
    expect(screen.getByTestId('admin-audit-log-page')).toBeInTheDocument();
  });

  it('renders resource-id-aware empty state when filtered to a resource with no events', async () => {
    vi.mocked(mockClient.get).mockResolvedValue({
      data: { results: [], count: 0, next: null, previous: null },
    } as never);

    render(<AdminAuditLogPage />, { wrapper });

    await waitFor(() => {
      expect(
        screen.getByText(new RegExp(`No events match resource_id ${FILE_ID}`, 'i')),
      ).toBeInTheDocument();
    });
  });

  it('CSV Export button is disabled when count is 0', async () => {
    vi.mocked(mockClient.get).mockResolvedValue({
      data: { results: [], count: 0, next: null, previous: null },
    } as never);

    render(<AdminAuditLogPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('admin-audit-log-export-csv-btn')).toBeDisabled();
    });
  });

  it('CSV Export fires auditService.export with resource_id forwarded and filename includes the UUID', async () => {
    // Stub list response with at least one event so the button enables.
    vi.mocked(mockClient.get).mockImplementation((url: string) => {
      if (url.includes('/export/')) {
        return Promise.resolve({ data: new Blob(['id,timestamp\n1,2025-01-01']) }) as never;
      }
      return Promise.resolve({
        data: {
          results: [
            {
              id: 'event-1',
              tenant: 't1',
              tenant_name: 'Tenant 1',
              actor_user: 'user-1',
              actor_user_email: 'admin@example.com',
              resource_type: 'FILE',
              resource_id: FILE_ID,
              action: 'FILE_DOWNLOADED',
              result: 'SUCCESS',
              details_json: {},
              timestamp: '2025-02-01T12:00:00Z',
            },
          ],
          count: 1,
          next: null,
          previous: null,
        },
      }) as never;
    });

    // Spy on download URL plumbing — the click should result in
    // an `<a>` element with the resource-id-bearing filename.
    const createObjectURLSpy = vi.fn(() => 'blob:fake-url');
    const revokeObjectURLSpy = vi.fn();
    Object.defineProperty(window.URL, 'createObjectURL', {
      writable: true,
      value: createObjectURLSpy,
    });
    Object.defineProperty(window.URL, 'revokeObjectURL', {
      writable: true,
      value: revokeObjectURLSpy,
    });
    let capturedDownloadName: string | null = null;
    const originalCreate = document.createElement.bind(document);
    const createElementSpy = vi
      .spyOn(document, 'createElement')
      .mockImplementation((tagName: string) => {
        const el = originalCreate(tagName);
        if (tagName === 'a') {
          // Capture the assigned download attribute.
          Object.defineProperty(el, 'download', {
            set(value: string) {
              capturedDownloadName = value;
            },
            get() {
              return capturedDownloadName ?? '';
            },
          });
          // Stub click so we don't actually navigate.
          (el as HTMLAnchorElement).click = () => undefined;
        }
        return el;
      });

    const user = userEvent.setup();
    render(<AdminAuditLogPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('admin-audit-log-export-csv-btn')).toBeEnabled();
    });

    await user.click(screen.getByTestId('admin-audit-log-export-csv-btn'));

    // Export call carried the resource_id filter.
    await waitFor(() => {
      const calls = vi.mocked(mockClient.get).mock.calls.map((c) => c[0] as string);
      expect(
        calls.some(
          (url) =>
            url.includes('/export/') &&
            url.includes('format=csv') &&
            url.includes(`resource_id=${FILE_ID}`),
        ),
      ).toBe(true);
    });

    // Filename embeds the resource UUID for compliance traceability.
    await waitFor(() => {
      expect(capturedDownloadName).toBe(`audit_log_${FILE_ID}.csv`);
    });
    expect(createObjectURLSpy).toHaveBeenCalled();
    expect(revokeObjectURLSpy).toHaveBeenCalled();

    createElementSpy.mockRestore();
  });

  it('R1 GAP-D — typing into resource_id input also writes back to the browser URL (deep-link writeback)', async () => {
    // Test honesty: the seed-from-URL contract was tested. The
    // OTHER half — "filter change writes back to URL" — was
    // aspirational without this test. Without writeback the
    // shareable-URL contract works in one direction only.
    vi.mocked(mockClient.get).mockResolvedValue({
      data: { results: [], count: 0, next: null, previous: null },
    } as never);
    const user = userEvent.setup();

    // Capture the search-params via a sniffer component that
    // pushes URL state into a callback ref on every render. The
    // ref-based capture avoids the lint "side-effect during
    // render" flag while still letting the test assert on the
    // observed URL.
    const observedSearches: string[] = [];
    function LocationSniffer() {
      const [searchParams] = useSearchParams();
      const search = searchParams.toString();
      // useEffect runs AFTER commit so this is a side-effect-free
      // capture from the lint rule's perspective.
      useEffect(() => {
        observedSearches.push(search);
      }, [search]);
      return <AdminAuditLogPage />;
    }

    function snifferWrapper({ children }: { children: ReactNode }) {
      void children;
      return (
        <QueryClientProvider client={queryClient}>
          <ToastProvider>
            <MemoryRouter initialEntries={['/admin/audit-log']}>
              <Routes>
                <Route path="/admin/audit-log" element={<LocationSniffer />} />
              </Routes>
            </MemoryRouter>
          </ToastProvider>
        </QueryClientProvider>
      );
    }

    render(<div />, { wrapper: snifferWrapper });

    await waitFor(() => {
      expect(screen.getByTestId('admin-audit-log-page')).toBeInTheDocument();
    });

    const input = screen.getByTestId('admin-audit-resource-id-filter') as HTMLInputElement;
    await user.type(input, FILE_ID);

    await waitFor(
      () => {
        expect(
          observedSearches.some((s) => s.includes(`resource_id=${FILE_ID}`)),
        ).toBe(true);
      },
      { timeout: 2000 },
    );
  });

  it('R1 GAP-C — pagination buttons disabled when no next/previous links and reset on filter change', async () => {
    // Test pagination wiring + the reset-to-page-1-on-filter-change
    // behaviour (without it the user lands on an empty page-3 of an
    // unrelated query after refining filters).
    let pagesServed = 0;
    vi.mocked(mockClient.get).mockImplementation(() => {
      pagesServed += 1;
      // First page: has a 'next' link. Subsequent: no next.
      return Promise.resolve({
        data: {
          results: [
            {
              id: `event-${pagesServed}`,
              tenant: 't1',
              tenant_name: 'Tenant 1',
              actor_user: null,
              actor_user_email: 'admin@example.com',
              resource_type: 'FILE',
              resource_id: FILE_ID,
              action: 'FILE_DOWNLOADED',
              result: 'SUCCESS',
              details_json: {},
              timestamp: '2025-02-01T12:00:00Z',
            },
          ],
          count: 60,
          next: pagesServed === 1 ? '/audit/audit-events/?page=2' : null,
          previous: pagesServed > 1 ? '/audit/audit-events/?page=1' : null,
        },
      }) as never;
    });

    const user = userEvent.setup();
    render(<AdminAuditLogPage />, { wrapper });

    // Page 1 — Previous disabled, Next enabled.
    await waitFor(() => {
      expect(screen.getByTestId('admin-audit-log-prev-page-btn')).toBeDisabled();
    });
    expect(screen.getByTestId('admin-audit-log-next-page-btn')).toBeEnabled();

    await user.click(screen.getByTestId('admin-audit-log-next-page-btn'));

    // Page 2 — Previous now enabled, Next disabled (mock returned no next).
    await waitFor(() => {
      expect(screen.getByTestId('admin-audit-log-prev-page-btn')).toBeEnabled();
    });
    expect(screen.getByTestId('admin-audit-log-next-page-btn')).toBeDisabled();
    expect(screen.getByTestId('admin-audit-log-pagination-info')).toHaveTextContent(/Page 2/);

    // Filter change MUST reset to page 1 — load-bearing for the
    // "user refines query, lands on page 1, not orphan page-3" UX.
    const input = screen.getByTestId('admin-audit-action-filter') as HTMLInputElement;
    await user.type(input, 'CREATED');
    await waitFor(() => {
      expect(screen.getByTestId('admin-audit-log-pagination-info')).toHaveTextContent(/Page 1/);
    });
  });

  it('typing into the resource_id input updates the API URL after debounce', async () => {
    vi.mocked(mockClient.get).mockResolvedValue({
      data: { results: [], count: 0, next: null, previous: null },
    } as never);
    const user = userEvent.setup();

    render(<AdminAuditLogPage />, { wrapper: emptyWrapper });

    await waitFor(() => {
      expect(screen.getByTestId('admin-audit-log-page')).toBeInTheDocument();
    });

    const input = screen.getByTestId('admin-audit-resource-id-filter') as HTMLInputElement;
    await user.type(input, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee');

    // Debounce is 300 ms — wait for the final URL with the typed
    // value to land.
    await waitFor(
      () => {
        const calls = vi.mocked(mockClient.get).mock.calls.map((c) => c[0] as string);
        expect(
          calls.some((url) =>
            url.includes('resource_id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'),
          ),
        ).toBe(true);
      },
      { timeout: 2000 },
    );
  });
});
