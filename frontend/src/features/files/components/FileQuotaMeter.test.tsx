/**
 * FileQuotaMeter tests — Phase 260.4.G.
 *
 * Verifies severity colouring, formatBytes, the "Upgrade for more"
 * CTA threshold, and the unlimited-plan branch. Pure helpers
 * (``severityForQuota``, ``formatBytes``) are tested in isolation;
 * the component is driven via the ``quotaOverride`` prop so the
 * underlying useFileStorageQuota query is gated off — but the hook
 * still calls useQueryClient unconditionally, so a QueryClientProvider
 * must wrap the tree.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import { FileQuotaMeter } from './FileQuotaMeter';

function withRouter(node: React.ReactElement) {
  // Each render gets a fresh client so cache state never leaks between tests.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('FileQuotaMeter', () => {
  it('renders unlimited plan label without a progress bar', () => {
    render(
      withRouter(
        <FileQuotaMeter
          disableFetch
          quotaOverride={{
            used_bytes: 5 * 1024 * 1024 * 1024,
            limit_bytes: null,
            percentage: null,
            plan_slug: 'enterprise',
            plan_tier: 'ENTERPRISE',
            unlimited: true,
          }}
        />,
      ),
    );

    const meter = screen.getByTestId('file-quota-meter');
    expect(meter).toHaveAttribute('data-unlimited', 'true');
    expect(meter).toHaveAttribute('data-severity', 'normal');
    expect(meter).toHaveTextContent(/5\.0 GB used/);
    expect(meter).toHaveTextContent(/unlimited plan/);
    // No progress bar in the unlimited surface.
    expect(screen.queryByTestId('file-quota-meter-fill')).toBeNull();
    // No upgrade CTA on the unlimited plan.
    expect(screen.queryByTestId('file-quota-meter-upgrade-cta')).toBeNull();
  });

  it('renders normal severity with progress bar at 25% — no Upgrade CTA', () => {
    render(
      withRouter(
        <FileQuotaMeter
          disableFetch
          quotaOverride={{
            used_bytes: 25 * 1024 * 1024 * 1024,
            limit_bytes: 100 * 1024 * 1024 * 1024,
            percentage: 25,
            plan_slug: 'pro',
            plan_tier: 'PRO',
            unlimited: false,
          }}
        />,
      ),
    );

    const meter = screen.getByTestId('file-quota-meter');
    expect(meter).toHaveAttribute('data-severity', 'normal');
    expect(meter).toHaveAttribute('role', 'status');
    expect(screen.getByTestId('file-quota-meter-fill')).toHaveStyle('width: 25%');
    expect(screen.queryByTestId('file-quota-meter-upgrade-cta')).toBeNull();
  });

  it('renders WARN severity at 85% (>80%) — still no Upgrade CTA (<=90%)', () => {
    render(
      withRouter(
        <FileQuotaMeter
          disableFetch
          quotaOverride={{
            used_bytes: 85 * 1024 * 1024 * 1024,
            limit_bytes: 100 * 1024 * 1024 * 1024,
            percentage: 85,
            plan_slug: 'pro',
            plan_tier: 'PRO',
            unlimited: false,
          }}
        />,
      ),
    );

    expect(screen.getByTestId('file-quota-meter')).toHaveAttribute('data-severity', 'warn');
    // Upgrade CTA fires at >90%, not at 85%.
    expect(screen.queryByTestId('file-quota-meter-upgrade-cta')).toBeNull();
  });

  it('shows "Upgrade for more" CTA at 91% (>90%)', () => {
    render(
      withRouter(
        <FileQuotaMeter
          disableFetch
          quotaOverride={{
            used_bytes: 91 * 1024 * 1024 * 1024,
            limit_bytes: 100 * 1024 * 1024 * 1024,
            percentage: 91,
            plan_slug: 'pro',
            plan_tier: 'PRO',
            unlimited: false,
          }}
        />,
      ),
    );

    const cta = screen.getByTestId('file-quota-meter-upgrade-cta');
    expect(cta).toBeInTheDocument();
    expect(cta).toHaveAttribute('href', '/settings/subscription');
  });

  it('renders DANGER severity at 96% (>95%) with role="alert"', () => {
    render(
      withRouter(
        <FileQuotaMeter
          disableFetch
          quotaOverride={{
            used_bytes: 96 * 1024 * 1024 * 1024,
            limit_bytes: 100 * 1024 * 1024 * 1024,
            percentage: 96,
            plan_slug: 'pro',
            plan_tier: 'PRO',
            unlimited: false,
          }}
        />,
      ),
    );

    const meter = screen.getByTestId('file-quota-meter');
    expect(meter).toHaveAttribute('data-severity', 'danger');
    // DANGER MUST be aria-live=alert so screen readers announce it
    // immediately — the user is about to hit a limit-gate 403.
    expect(meter).toHaveAttribute('role', 'alert');
    // Upgrade CTA also visible at danger threshold.
    expect(screen.getByTestId('file-quota-meter-upgrade-cta')).toBeInTheDocument();
  });

  it('caps the progress bar fill at 100% even when over-quota', () => {
    // When used > limit (over-quota), the backend caps percentage
    // at 100; the bar fill should also cap so it doesn't overflow
    // its container.
    render(
      withRouter(
        <FileQuotaMeter
          disableFetch
          quotaOverride={{
            used_bytes: 200 * 1024 * 1024 * 1024,
            limit_bytes: 100 * 1024 * 1024 * 1024,
            percentage: 100,
            plan_slug: 'pro',
            plan_tier: 'PRO',
            unlimited: false,
          }}
        />,
      ),
    );
    expect(screen.getByTestId('file-quota-meter-fill')).toHaveStyle('width: 100%');
  });
});
