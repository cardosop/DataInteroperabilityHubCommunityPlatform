/**
 * MyApprovalsInbox Tests — the inbox-root testid contract
 * (close-test-coverage-gaps 2.2).
 *
 * Real useAccessRequests hook and real governanceService; only the API
 * client is mocked (the sanctioned component-test seam — no mocks of
 * application code). The pin locks the E2E selector contract:
 * `data-testid="my-approvals-inbox"` renders on the loaded AND empty
 * states (bulk-approve-reject / approval-inbox-unified / a11y specs
 * select it), with `.my-approvals-inbox__empty` for the empty state.
 * A regression that drops the testid from either state fails here.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AccessRequest } from '../../../shared/types/governance';
import { MyApprovalsInbox } from './MyApprovalsInbox';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';

function makeAccessRequest(overrides: Partial<AccessRequest> = {}): AccessRequest {
  return {
    id: 'ar-1',
    tenant: 'tenant-1',
    requested_by: 'user-1',
    asset: null,
    dataset: null,
    file: null,
    reason: 'Need read access for analytics',
    requested_access_type: 'read',
    status: 'PENDING',
    requires_approval: true,
    approval_workflow: null,
    current_approval_step: 0,
    approvers: null,
    approved_by: null,
    approved_at: null,
    rejected_by: null,
    rejected_at: null,
    rejection_reason: null,
    expires_at: null,
    access_granted_at: null,
    order: null,
    created_at: '2026-09-28T10:00:00Z',
    updated_at: '2026-09-28T10:00:00Z',
    ...overrides,
  };
}

describe('MyApprovalsInbox', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  function renderInbox() {
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <MyApprovalsInbox />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it('renders the inbox root with the my-approvals-inbox testid (loaded state)', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValueOnce({
      data: { results: [makeAccessRequest()] },
    });

    renderInbox();

    const root = await screen.findByTestId('my-approvals-inbox');
    expect(root).toBeInTheDocument();
    expect(root.className).toContain('my-approvals-inbox');
    // The loaded item row renders inside the same root.
    expect(await screen.findByText(/Need read access/)).toBeInTheDocument();
  });

  it('renders the inbox root with the same testid in the empty state', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValueOnce({
      data: { results: [] },
    });

    renderInbox();

    const root = await screen.findByTestId('my-approvals-inbox');
    expect(root).toBeInTheDocument();
    expect(
      root.querySelector('.my-approvals-inbox__empty'),
    ).toBeInTheDocument();
  });

  it('shows the loading spinner before the list resolves', () => {
    vi.mocked(apiClient.getClient().get).mockReturnValueOnce(
      new Promise(() => {}),
    );

    renderInbox();

    expect(screen.queryByTestId('my-approvals-inbox')).not.toBeInTheDocument();
    expect(screen.getByText(/Loading approvals/)).toBeInTheDocument();
  });

  it('shows the error display when the list fetch fails', async () => {
    vi.mocked(apiClient.getClient().get).mockRejectedValueOnce(
      new Error('Network Error'),
    );

    renderInbox();

    expect(await screen.findByText(/Failed to load approvals/)).toBeInTheDocument();
    expect(screen.queryByTestId('my-approvals-inbox')).not.toBeInTheDocument();
  });
});
