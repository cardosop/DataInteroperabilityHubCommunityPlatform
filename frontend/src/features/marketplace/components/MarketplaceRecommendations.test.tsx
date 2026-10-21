/**
 * W5.4 (R2-F5) — recommendation feedback pending-state pins.
 *
 * Pre-fix the 👍/👎 buttons had NO pending guard: a rapid double-click
 * fired duplicate feedback votes. Pins: while a vote is in flight the
 * buttons disable and a second click cannot fire another mutation.
 * Only the recommendationsService HTTP seam is stubbed.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/recommendationsService');

import { recommendationsService } from '../services/recommendationsService';
import { MarketplaceRecommendations } from './MarketplaceRecommendations';

function wrap(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

describe('MarketplaceRecommendations pending states (W5.4)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    vi.mocked(recommendationsService.getRecommendations).mockResolvedValue({
      you_might_also_like: [],
      trending: [
        {
          id: 'l1',
          listing_id: 'l1',
          title: 'Trending dataset',
          reasons: [],
        },
      ],
    } as never);
  });

  it('disables the feedback buttons while a vote is in flight (no duplicate votes)', async () => {
    const user = userEvent.setup();
    let resolveFeedback: (value: unknown) => void = () => {};
    const submitFeedbackMock = vi.mocked(recommendationsService.submitFeedback);
    submitFeedbackMock.mockImplementation(
      () => new Promise((resolve) => {
        resolveFeedback = resolve;
      }),
    );

    render(<MarketplaceRecommendations />, { wrapper: wrap(queryClient) });

    const helpfulBtn = await screen.findByRole('button', { name: 'Helpful' });
    await user.click(helpfulBtn);

    // In flight: every feedback button is disabled.
    expect(screen.getByRole('button', { name: 'Helpful' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Not helpful' })).toBeDisabled();

    // A rapid second click must not fire a second mutation.
    await user.click(screen.getByRole('button', { name: 'Not helpful' })).catch(() => {});
    expect(submitFeedbackMock).toHaveBeenCalledTimes(1);

    resolveFeedback({});
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Helpful' })).not.toBeDisabled();
    });
  });
});
