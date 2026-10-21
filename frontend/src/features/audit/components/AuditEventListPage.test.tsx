/**
 * W5.4 (R2-F5) — real audit pagination.
 *
 * Pre-fix the /audit page shipped placeholder pagination: the page
 * number was hardcoded to 1 and the Next/Previous buttons were
 * ``console.log`` stubs — rows beyond the first 20 were unreachable.
 *
 * These pins run the REAL useAuditEvents hook + query client through
 * the apiClient HTTP seam (the AdminAuditLogPage pattern): clicking
 * Next must fetch page 2, the buttons must derive their disabled state
 * from the wire next/previous links, and a filter change must reset to
 * page 1.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../../shared/components/Toast';
import type { AuditEvent, AuditEventListResponse } from '../../../shared/types/audit';
import { AuditEventListPage } from './AuditEventListPage';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';

function makeEvent(id: string, action: string): AuditEvent {
  return {
    id,
    tenant: 'tenant-a',
    tenant_name: 'Tenant A',
    actor_user: null,
    actor_user_email: null,
    resource_type: 'ASSET',
    resource_id: null,
    action,
    result: 'SUCCESS',
    details_json: {},
    timestamp: '2026-10-12T10:00:00Z',
  };
}

function makePage(
  results: AuditEvent[],
  { count, next, previous }: { count: number; next: string | null; previous: string | null },
): AuditEventListResponse {
  return { count, next, previous, results };
}

describe('AuditEventListPage — real pagination (W5.4)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={['/audit']}>
            <Routes>
              <Route path="/audit" element={children} />
              <Route path="/audit/:id" element={<div>detail</div>} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>
    );
  }

  it('fetches page 2 when Next is clicked (rows beyond page 1 are reachable)', async () => {
    const user = userEvent.setup();
    const getMock = vi.mocked(apiClient.getClient().get);
    getMock
      .mockResolvedValueOnce({
        data: makePage([makeEvent('evt-a', 'LOGIN')], {
          count: 21,
          next: 'http://x/api/v1/audit/events/?page=2',
          previous: null,
        }),
        status: 200,
        headers: {},
      })
      .mockResolvedValueOnce({
        data: makePage([makeEvent('evt-b', 'LOGOUT')], {
          count: 21,
          next: null,
          previous: 'http://x/api/v1/audit/events/?page=1',
        }),
        status: 200,
        headers: {},
      });

    render(<AuditEventListPage />, { wrapper });

    await screen.findByText('LOGIN');
    await user.click(screen.getByRole('button', { name: 'Next' }));

    await screen.findByText('LOGOUT');
    // The second request carried page=2 in the wire URL — real server-side
    // pagination, not a client-side slice.
    const page2Call = getMock.mock.calls[1];
    expect(page2Call[0]).toMatch(/page=2\b/);
  });

  it('disables Next/Previous from the wire next/previous links', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: makePage([makeEvent('evt-a', 'LOGIN')], { count: 1, next: null, previous: null }),
      status: 200,
      headers: {},
    });

    render(<AuditEventListPage />, { wrapper });

    await screen.findByText('LOGIN');
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
  });

  it('resets to page 1 when a filter changes', async () => {
    const user = userEvent.setup();
    const getMock = vi.mocked(apiClient.getClient().get);
    getMock
      .mockResolvedValueOnce({
        data: makePage([makeEvent('evt-a', 'LOGIN')], {
          count: 21,
          next: 'http://x/api/v1/audit/events/?page=2',
          previous: null,
        }),
        status: 200,
        headers: {},
      })
      .mockResolvedValueOnce({
        data: makePage([makeEvent('evt-b', 'LOGOUT')], {
          count: 21,
          next: null,
          previous: 'http://x/api/v1/audit/events/?page=1',
        }),
        status: 200,
        headers: {},
      })
      // The filter change refetches once with the OLD page (parity with
      // the sibling AdminAuditLogPage reset effect) and once more after
      // the reset lands on page 1.
      .mockResolvedValueOnce({
        data: makePage([makeEvent('evt-c', 'VIEWED')], {
          count: 1,
          next: null,
          previous: null,
        }),
        status: 200,
        headers: {},
      })
      .mockResolvedValueOnce({
        data: makePage([makeEvent('evt-c', 'VIEWED')], {
          count: 1,
          next: null,
          previous: null,
        }),
        status: 200,
        headers: {},
      });

    render(<AuditEventListPage />, { wrapper });

    await screen.findByText('LOGIN');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await screen.findByText('LOGOUT');

    // Change a discrete filter — the page must reset to 1.
    await user.selectOptions(screen.getByLabelText('Filter by resource type'), 'CONTRACT');

    await screen.findByText('VIEWED');
    // The FINAL post-filter request carried page=1, not page=2.
    const calls = getMock.mock.calls;
    expect(calls[calls.length - 1][0]).toMatch(/page=1\b/);
    expect(calls[calls.length - 1][0]).not.toMatch(/page=2\b/);
  });
});
