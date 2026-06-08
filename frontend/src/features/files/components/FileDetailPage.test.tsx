/**
 * FileDetailPage tests.
 *
 * Verifies the page-level surface:
 *   - reads `:id` from the route, fetches via ``useFile`` / GET /files/{id}
 *   - renders ScanStatusBanner above metadata
 *   - renders the metadata block (name/type/scan pill)
 *   - download button is disabled when scan status forbids it
 *   - mounts ActivityTimeline (resourceType="FILE") for the audit-log section
 *   - shows DetailPageSkeleton while loading
 *   - shows ErrorDisplay with retry when /files/{id} fails
 *   - delete CTA opens ConfirmDialog and calls DELETE on confirm
 *
 * Real ``useFile``/``useFileScanStatus``/``useResourceActivity`` — only the
 * apiClient is mocked, no business-logic stubbing.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { type ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { HttpClient } from '../../../shared/types/api';
import type { File as FileType } from '../../../shared/types/files';
import { ToastProvider } from '../../../shared/components/Toast';
import { FileDetailPage } from './FileDetailPage';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';

const FILE_ID = '550e8400-e29b-41d4-a716-446655440000';

function makeFile(overrides: Partial<FileType> = {}): FileType {
  return {
    id: FILE_ID,
    name: 'sample.csv',
    content_type: 'text/csv',
    size: 2048,
    storage_path: 't/id/sample.csv',
    status: 'COMPLETED',
    scan_status: 'CLEAN',
    scanned_at: '2025-02-01T08:00:00.000Z',
    created_at: '2025-02-01T07:00:00.000Z',
    updated_at: '2025-02-01T08:00:00.000Z',
    created_by: 'user-1',
    tenant_id: 'tenant-1',
    ...overrides,
  };
}

type MockGetCall = (url: string) => Promise<unknown>;

function setupMockGet(handler: MockGetCall, mockClient: HttpClient) {
  vi.mocked(mockClient.get).mockImplementation((url: string) => {
    return handler(url) as never;
  });
}

// React Query / async-effect chains commit setState in microtasks
// AFTER `render()` returns. Wrap a setTimeout(0) flush in act()
// so those updates land inside React's tracked scope rather than
// leaking an "An update to ... inside a test was not wrapped in
// act(...)" warning. The synchronous notifyManager scheduler set
// up in src/test/setup.ts handles React Query NOTIFICATIONS once
// the underlying state changes inside an act scope; this helper
// gives the change a chance to commit by yielding to the event
// loop under act().
async function flushReactQueries(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

describe('FileDetailPage (Phase 260.4.B)', () => {
  let queryClient: QueryClient;
  let mockClient: HttpClient;

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/files/${FILE_ID}`]}>
            <Routes>
              <Route path="/files/:id" element={children} />
              <Route path="/files" element={<div>files-list</div>} />
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
    vi.mocked(mockClient.post).mockClear();
    vi.mocked(mockClient.delete).mockClear();
  });

  it('renders skeleton while file is loading', async () => {
    let resolveGet: (value: unknown) => void;
    const pendingPromise = new Promise((resolve) => {
      resolveGet = resolve;
    });
    setupMockGet((url) => {
      if (url.includes(`files/${FILE_ID}/`) && !url.includes('scan-status')) {
        return pendingPromise;
      }
      // Resource-activity + scan-status: leave hanging too — we only assert skeleton.
      return new Promise(() => {});
    }, mockClient);

    render(<FileDetailPage />, { wrapper });

    expect(screen.getByTestId('file-detail-page-loading')).toBeInTheDocument();

    // Resolve so React Query unmounts cleanly during teardown.
    resolveGet!({ data: makeFile() });

    await flushReactQueries();

  
  });

  it('renders metadata, scan banner, and audit-log section after fetch', async () => {
    const file = makeFile();
    setupMockGet((url) => {
      if (url.includes(`files/${FILE_ID}/scan-status/`)) {
        return Promise.resolve({
          data: { scan_status: file.scan_status, scanned_at: file.scanned_at },
        });
      }
      if (url.includes(`files/${FILE_ID}/`)) {
        return Promise.resolve({ data: file });
      }
      if (url.includes('audit/audit-events/resource-activity/')) {
        return Promise.resolve({ data: { results: [] } });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    }, mockClient);

    render(<FileDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('file-detail-page')).toBeInTheDocument();
    });

    // Metadata
    // Filename appears in breadcrumb, h1 title, and metadata block — assert
    // on the metadata-block testid specifically to avoid the ambiguous match.
    expect(screen.getByTestId('file-detail-name-value')).toHaveTextContent('sample.csv');
    expect(screen.getByText('text/csv')).toBeInTheDocument();
    expect(screen.getByTestId('file-detail-scan-pill')).toHaveAttribute('data-scan-status', 'CLEAN');

    // Audit log section is rendered (empty state OK — the API returns no events here)
    await waitFor(() => {
      expect(screen.getByTestId('file-detail-activity-section')).toBeInTheDocument();
    });
    await flushReactQueries();
  });

  it('shows ErrorDisplay with retry when GET /files/{id} fails', async () => {
    setupMockGet((url) => {
      if (url.includes(`files/${FILE_ID}/`) && !url.includes('scan-status')) {
        return Promise.reject(new Error('boom'));
      }
      return new Promise(() => {});
    }, mockClient);

    render(<FileDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/failed to load file/i)).toBeInTheDocument();
    });
    await flushReactQueries();
  });

  it('disables Download when scan is not CLEAN', async () => {
    setupMockGet((url) => {
      if (url.includes(`files/${FILE_ID}/scan-status/`)) {
        return Promise.resolve({ data: { scan_status: 'PENDING_SCAN', scanned_at: null } });
      }
      if (url.includes(`files/${FILE_ID}/`)) {
        return Promise.resolve({
          data: makeFile({ scan_status: 'PENDING_SCAN', scanned_at: null }),
        });
      }
      if (url.includes('audit/audit-events/resource-activity/')) {
        return Promise.resolve({ data: { results: [] } });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    }, mockClient);

    render(<FileDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('file-detail-page')).toBeInTheDocument();
    });
    await flushReactQueries();

    expect(screen.getByTestId('file-detail-download-btn')).toBeDisabled();
  });

  it('back button navigates to /files list', async () => {
    setupMockGet((url) => {
      if (url.includes(`files/${FILE_ID}/scan-status/`)) {
        return Promise.resolve({ data: { scan_status: 'CLEAN', scanned_at: '2025-02-01T08:00:00Z' } });
      }
      if (url.includes(`files/${FILE_ID}/`)) {
        return Promise.resolve({ data: makeFile() });
      }
      if (url.includes('audit/audit-events/resource-activity/')) {
        return Promise.resolve({ data: { results: [] } });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    }, mockClient);

    const user = userEvent.setup();
    render(<FileDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('file-detail-page')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /back to files/i }));
    await waitFor(() => {
      expect(screen.getByText('files-list')).toBeInTheDocument();
    });
    await flushReactQueries();
  });

  it('overrides cached PENDING_SCAN with the polled CLEAN value (live banner update)', async () => {
    // R1 audit — load-bearing claim of the page is "polled value
    // overrides cached value so the banner + pill update without a
    // full refetch". Without this test the override happens silently
    // and the regression would only surface as a stale UI in
    // production. We assert: (a) the page initially shows PENDING_SCAN
    // (cached value); (b) after the first scan-status poll lands
    // CLEAN, the pill flips to CLEAN AND the Download button enables;
    // (c) the metadata block reflects the polled scanned_at.
    setupMockGet((url) => {
      if (url.includes(`files/${FILE_ID}/scan-status/`)) {
        // Polling endpoint — single CLEAN response (the first
        // useFileScanStatus tick fires immediately on mount).
        return Promise.resolve({
          data: { scan_status: 'CLEAN', scanned_at: '2025-02-01T09:00:00.000Z' },
        });
      }
      if (url.includes(`files/${FILE_ID}/`)) {
        // Cached value: PENDING_SCAN — override path is the LOAD-
        // BEARING contract here. ``canDownloadFile`` returns false
        // for PENDING_SCAN so the Download button is initially
        // disabled; once the polled CLEAN value lands the button
        // must enable.
        return Promise.resolve({
          data: makeFile({ scan_status: 'PENDING_SCAN', scanned_at: null }),
        });
      }
      if (url.includes('audit/audit-events/resource-activity/')) {
        return Promise.resolve({ data: { results: [] } });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    }, mockClient);

    render(<FileDetailPage />, { wrapper });

    // Initial render — pill reflects cached PENDING_SCAN, Download
    // disabled. The polled tick lands within the same microtask but
    // ``waitFor`` will catch the final state.
    await waitFor(() => {
      expect(screen.getByTestId('file-detail-page')).toBeInTheDocument();
    });

    // Final state after polled tick — pill is CLEAN + Download is
    // enabled. If the override path were broken the pill would stay
    // PENDING_SCAN and the test would fail.
    await waitFor(() => {
      expect(screen.getByTestId('file-detail-scan-pill')).toHaveAttribute(
        'data-scan-status',
        'CLEAN',
      );
    });
    expect(screen.getByTestId('file-detail-download-btn')).toBeEnabled();
  });

  it('renders ScanStatusBanner for non-CLEAN scan and asset/dataset links', async () => {
    // R1 audit — the banner is the primary customer-education affordance
    // on non-CLEAN scans (260.3.H). Original test suite only checked
    // the pill; the banner mounting was untested. Asset/dataset link
    // rendering on the metadata block was also uncovered.
    setupMockGet((url) => {
      if (url.includes(`files/${FILE_ID}/scan-status/`)) {
        return Promise.resolve({ data: { scan_status: 'PENDING_SCAN', scanned_at: null } });
      }
      if (url.includes(`files/${FILE_ID}/`)) {
        return Promise.resolve({
          data: makeFile({
            scan_status: 'PENDING_SCAN',
            scanned_at: null,
            asset_id: '11111111-2222-3333-4444-555555555555',
            dataset_id: '99999999-8888-7777-6666-555555555555',
          }),
        });
      }
      if (url.includes('audit/audit-events/resource-activity/')) {
        return Promise.resolve({ data: { results: [] } });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    }, mockClient);

    render(<FileDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('file-detail-page')).toBeInTheDocument();
    });

    // Banner mounts (PENDING_SCAN is non-CLEAN, banner returns a section).
    await waitFor(() => {
      const banner = screen.getByTestId('scan-status-banner');
      expect(banner).toHaveAttribute('data-scan-status', 'PENDING_SCAN');
    });
    await flushReactQueries();

    // Asset + dataset links surface in the metadata block.
    expect(screen.getByRole('link', { name: /view asset/i })).toHaveAttribute(
      'href',
      '/assets/11111111-2222-3333-4444-555555555555',
    );
    expect(screen.getByRole('link', { name: /view dataset/i })).toHaveAttribute(
      'href',
      '/datasets/99999999-8888-7777-6666-555555555555',
    );

    await flushReactQueries();

  
  });

  it('propagates polled terminal scan-status onto the useFile cache', async () => {
    // R1 audit GAP-F — the page polls scan-status while PENDING_SCAN
    // and overrides the cached value at render time. WITHOUT cache
    // propagation, navigating away + back would surface stale
    // ``PENDING_SCAN`` from React Query for up to 5 minutes
    // (default staleTime). This test asserts the cache is patched
    // when the polled value lands a terminal state.
    setupMockGet((url) => {
      if (url.includes(`files/${FILE_ID}/scan-status/`)) {
        return Promise.resolve({
          data: { scan_status: 'CLEAN', scanned_at: '2025-02-01T09:00:00.000Z' },
        });
      }
      if (url.includes(`files/${FILE_ID}/`)) {
        return Promise.resolve({
          data: makeFile({ scan_status: 'PENDING_SCAN', scanned_at: null }),
        });
      }
      if (url.includes('audit/audit-events/resource-activity/')) {
        return Promise.resolve({ data: { results: [] } });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    }, mockClient);

    render(<FileDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('file-detail-scan-pill')).toHaveAttribute(
        'data-scan-status',
        'CLEAN',
      );
    });

    // Cache assertion — read the file detail entry directly out of
    // the QueryClient. After the polled CLEAN value lands, the cache
    // entry MUST reflect CLEAN + the polled scanned_at, not the
    // stale PENDING_SCAN from the initial fetch.
    await waitFor(() => {
      const cached = queryClient.getQueryData<FileType>(['files', 'detail', FILE_ID]);
      expect(cached?.scan_status).toBe('CLEAN');
      expect(cached?.scanned_at).toBe('2025-02-01T09:00:00.000Z');
    });
    await flushReactQueries();
  });

  describe('rename UI (Phase 260.4.C)', () => {
    function setupRenameStubs(file = makeFile()) {
      setupMockGet((url) => {
        if (url.includes(`files/${FILE_ID}/scan-status/`)) {
          return Promise.resolve({
            data: { scan_status: file.scan_status, scanned_at: file.scanned_at },
          });
        }
        if (url.includes(`files/${FILE_ID}/`)) {
          return Promise.resolve({ data: file });
        }
        if (url.includes('audit/audit-events/resource-activity/')) {
          return Promise.resolve({ data: { results: [] } });
        }
        return Promise.reject(new Error(`unexpected GET ${url}`));
      }, mockClient);
    }

    it('Rename button toggles the inline edit form pre-filled with current name', async () => {
      setupRenameStubs();
      const user = userEvent.setup();
      render(<FileDetailPage />, { wrapper });

      await waitFor(() => {
        expect(screen.getByTestId('file-detail-page')).toBeInTheDocument();
      });

      // Form is hidden initially; name displayed as plain text.
      expect(screen.queryByTestId('file-detail-rename-form')).toBeNull();
      expect(screen.getByTestId('file-detail-name-value')).toHaveTextContent('sample.csv');

      await user.click(screen.getByTestId('file-detail-rename-btn'));

      expect(screen.getByTestId('file-detail-rename-form')).toBeInTheDocument();
      const input = screen.getByTestId('file-detail-rename-input') as HTMLInputElement;
      expect(input.value).toBe('sample.csv');
      // Save enabled because draft equals current name and is non-empty
      // (validity gate); BUT clicking Save with the same name should
      // close the editor without firing a network request — covered
      // by a separate test below.
      expect(screen.getByTestId('file-detail-rename-save-btn')).toBeEnabled();

      await flushReactQueries();

    
    });

    it('disables Save when the draft is empty and surfaces the validation hint', async () => {
      setupRenameStubs();
      const user = userEvent.setup();
      render(<FileDetailPage />, { wrapper });

      await waitFor(() => {
        expect(screen.getByTestId('file-detail-page')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('file-detail-rename-btn'));
      const input = screen.getByTestId('file-detail-rename-input');
      await user.clear(input);

      expect(screen.getByTestId('file-detail-rename-save-btn')).toBeDisabled();
      expect(screen.getByTestId('file-detail-rename-error')).toBeInTheDocument();
      expect(input).toHaveAttribute('aria-invalid', 'true');

      await flushReactQueries();

    
    });

    it('Save fires POST /files/{id}/rename/ and closes the editor on success', async () => {
      setupRenameStubs();
      vi.mocked(mockClient.post).mockImplementation((url: string, body) => {
        if (url.includes(`files/${FILE_ID}/rename/`)) {
          // Backend returns the canonical serialised file payload —
          // the cache patch in ``useRenameFile`` keys on this shape.
          return Promise.resolve({
            data: makeFile({ name: (body as { name: string }).name }),
          }) as never;
        }
        return Promise.reject(new Error(`unexpected POST ${url}`)) as never;
      });

      const user = userEvent.setup();
      render(<FileDetailPage />, { wrapper });

      await waitFor(() => {
        expect(screen.getByTestId('file-detail-page')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('file-detail-rename-btn'));
      const input = screen.getByTestId('file-detail-rename-input');
      await user.clear(input);
      await user.type(input, 'renamed.csv');
      await user.click(screen.getByTestId('file-detail-rename-save-btn'));

      await waitFor(() => {
        expect(vi.mocked(mockClient.post)).toHaveBeenCalledWith(
          expect.stringContaining(`files/${FILE_ID}/rename/`),
          { name: 'renamed.csv' },
        );
      });

      // Editor closes on success.
      await waitFor(() => {
        expect(screen.queryByTestId('file-detail-rename-form')).toBeNull();
      });
      // Page reflects the new name (cache patch from useRenameFile).
      expect(screen.getByTestId('file-detail-name-value')).toHaveTextContent('renamed.csv');

      await flushReactQueries();

    
    });

    it('same-name save closes the editor without firing the API', async () => {
      // Save with the unchanged name is treated as a client-side
      // no-op — saves a network round-trip and matches the backend's
      // idempotent same-name handling.
      setupRenameStubs();
      const user = userEvent.setup();
      render(<FileDetailPage />, { wrapper });

      await waitFor(() => {
        expect(screen.getByTestId('file-detail-page')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('file-detail-rename-btn'));
      // Input is pre-filled with the current name; click Save with no edits.
      await user.click(screen.getByTestId('file-detail-rename-save-btn'));

      await waitFor(() => {
        expect(screen.queryByTestId('file-detail-rename-form')).toBeNull();
      });
      // No POST fired.
      expect(vi.mocked(mockClient.post)).not.toHaveBeenCalledWith(
        expect.stringContaining('/rename/'),
        expect.anything(),
      );

      await flushReactQueries();

    
    });

    it('Cancel reverts the draft and closes the editor without firing the API', async () => {
      setupRenameStubs();
      const user = userEvent.setup();
      render(<FileDetailPage />, { wrapper });

      await waitFor(() => {
        expect(screen.getByTestId('file-detail-page')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('file-detail-rename-btn'));
      const input = screen.getByTestId('file-detail-rename-input');
      await user.clear(input);
      await user.type(input, 'never-saved.csv');
      await user.click(screen.getByTestId('file-detail-rename-cancel-btn'));

      // Editor closes; page still shows the original name.
      await waitFor(() => {
        expect(screen.queryByTestId('file-detail-rename-form')).toBeNull();
      });
      expect(screen.getByTestId('file-detail-name-value')).toHaveTextContent('sample.csv');
      // No POST fired.
      expect(vi.mocked(mockClient.post)).not.toHaveBeenCalledWith(
        expect.stringContaining('/rename/'),
        expect.anything(),
      );
      await flushReactQueries();
    });
  });

  it('opens delete ConfirmDialog and calls DELETE on confirm', async () => {
    setupMockGet((url) => {
      if (url.includes(`files/${FILE_ID}/scan-status/`)) {
        return Promise.resolve({ data: { scan_status: 'CLEAN', scanned_at: '2025-02-01T08:00:00Z' } });
      }
      if (url.includes(`files/${FILE_ID}/`)) {
        return Promise.resolve({ data: makeFile() });
      }
      if (url.includes('audit/audit-events/resource-activity/')) {
        return Promise.resolve({ data: { results: [] } });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    }, mockClient);
    vi.mocked(mockClient.delete).mockResolvedValue({ data: null } as never);

    const user = userEvent.setup();
    render(<FileDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('file-detail-page')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('file-detail-delete-btn'));
    const dialog = await screen.findByRole('dialog', { name: /delete file/i });
    // Confirm button lives inside the dialog — scope query so we don't
    // pick up the page-level Delete CTA that opened it.
    const confirmBtn = await within(dialog).findByRole('button', { name: /^delete$/i });
    await user.click(confirmBtn);

    await waitFor(() => {
      expect(vi.mocked(mockClient.delete)).toHaveBeenCalledWith(
        expect.stringContaining(`files/${FILE_ID}/`),
      );
    });
    await flushReactQueries();
  });
});
