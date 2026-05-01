/**
 * Phase 228.F3.DoD.1-C + DoD.1-D — frontend assertions for the
 * LineageSubscriptionPanel surface.
 *
 * Pinned spec scenarios:
 *
 * - REQ-LIN-F3-006 "Subscribe button visible": when capability
 *   `lineage.change_notifications` is ON, the panel renders the
 *   "Subscribe to lineage changes" CTA.  When OFF, the panel
 *   renders nothing (no UI surface — the F3 capability gate is the
 *   kill-switch).
 *
 * - REQ-LIN-F3-008 "Slack option not exposed in v1": the panel
 *   does NOT render any Slack-channel toggle.  The schema field
 *   exists in the backend for forward-compat (v2) but the v1 UI
 *   must not surface it.
 *
 * No mocks of internal logic — only the apiClient HTTP seam +
 * `useCapabilities` are stubbed (the latter is the single source
 * of truth for flag state; the panel's behaviour is a pure
 * function of that flag).
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');
vi.mock('../../../shared/hooks/useCapabilities');

import { apiClient } from '../../../shared/api/client';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import { LineageSubscriptionPanel } from './LineageSubscriptionPanel';

function wrap(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

function setCapabilityState(enabled: boolean) {
  vi.mocked(useCapabilities).mockReturnValue({
    capabilities: {},
    isLoading: false,
    isCapabilityAvailable: (key: string) =>
      key === 'lineage.change_notifications' ? enabled : false,
    getCapability: () => undefined,
  });
}

describe('LineageSubscriptionPanel — capability gating + v1 channel scope', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    // Default: empty subscription list response.
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: {
        count: 0,
        next_cursor: null,
        previous_cursor: null,
        page_size: 50,
        results: [],
      },
    } as never);
  });

  it('renders the Subscribe CTA when capability is ON', async () => {
    setCapabilityState(true);

    render(
      <LineageSubscriptionPanel sourceContractId="c-1" />,
      { wrapper: wrap(queryClient) },
    );

    await waitFor(() => {
      expect(screen.getByTestId('lineage-subscription-panel')).toBeInTheDocument();
    });
    expect(screen.getByTestId('lineage-subscribe')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /subscribe to lineage changes/i }),
    ).toBeInTheDocument();
  });

  it('renders nothing when capability is OFF', () => {
    setCapabilityState(false);

    const { container } = render(
      <LineageSubscriptionPanel sourceContractId="c-1" />,
      { wrapper: wrap(queryClient) },
    );
    // The panel returns null when the flag is off.
    expect(container.querySelector('[data-testid="lineage-subscription-panel"]')).toBeNull();
  });

  // REQ-LIN-F3-008 "Slack option not exposed in v1".
  it('does not expose any Slack channel toggle', async () => {
    setCapabilityState(true);

    render(
      <LineageSubscriptionPanel sourceContractId="c-1" />,
      { wrapper: wrap(queryClient) },
    );
    await screen.findByTestId('lineage-subscription-panel');

    // No Slack toggle / button / label in the DOM.
    expect(screen.queryByText(/slack/i)).toBeNull();
    expect(
      screen.queryByRole('checkbox', { name: /slack/i }),
    ).toBeNull();
  });
});
