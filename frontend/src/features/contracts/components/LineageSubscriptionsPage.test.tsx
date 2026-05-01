/**
 * Phase 228.F3.DoD.1-D — REQ-LIN-F3-008 "Slack option not exposed in v1"
 * assertion for the LineageSubscriptionsPage table.
 *
 * The page renders one row per subscription with columns:
 *   Source | Severity | In-app | Email | Last dispatched | Actions
 *
 * Slack must NOT be a column AND no Slack-toggle/label must appear
 * in any row even when the API returns `slack: true` (the schema
 * field exists for forward-compat with v2; the v1 UI must ignore it).
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');
vi.mock('../../../shared/hooks/useCapabilities');

import { apiClient } from '../../../shared/api/client';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import { LineageSubscriptionsPage } from './LineageSubscriptionsPage';

function wrap(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

describe('LineageSubscriptionsPage — REQ-LIN-F3-008 Slack v1 scope', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.mocked(useCapabilities).mockReturnValue({
      capabilities: {},
      isLoading: false,
      isCapabilityAvailable: (k: string) => k === 'lineage.change_notifications',
      getCapability: () => undefined,
    });
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: {
        count: 1,
        next_cursor: null,
        previous_cursor: null,
        page_size: 50,
        results: [
          {
            id: 'sub-1',
            user: 'u1',
            source_contract: 'c-42',
            source_asset: null,
            severity_threshold: 'HIGH',
            in_app: true,
            email: false,
            // Server returns the field for forward-compat — UI must
            // still NOT surface it.
            slack: true,
            created_at: new Date().toISOString(),
            last_dispatched_at: null,
          },
        ],
      },
    } as never);
  });

  it('does not render a Slack column or toggle', async () => {
    render(<LineageSubscriptionsPage />, { wrapper: wrap(queryClient) });

    // Row should be present.
    const row = await screen.findByTestId('lineage-subscription-row-sub-1');
    expect(row).toBeInTheDocument();

    // No Slack header.
    const headers = Array.from(row.closest('table')?.querySelectorAll('th') ?? [])
      .map((th) => th.textContent?.toLowerCase() ?? '');
    expect(headers).not.toContain('slack');

    // No Slack-related checkbox / label anywhere on the page.
    expect(screen.queryByRole('checkbox', { name: /slack/i })).toBeNull();
    expect(screen.queryByText(/slack/i)).toBeNull();
  });
});
