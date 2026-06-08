/**
 * Phase 235.5 — frontend test for the consolidated PLATFORM_ADMIN
 * dashboard widget grid.
 *
 * Spec 235.5.10 ("Tests: widgets render with seeded data; cache hit
 * avoids regeneration") is covered HERE for the SPA half:
 *
 * 1.  ``renders all six widgets with counts from a seeded summary
 *      response`` — confirms the SPA decodes the aggregate shape and
 *      surfaces counts to the operator.
 * 2.  ``cache-hit response renders the (cached) badge`` — confirms the
 *      ``cache_hit`` discriminator drives the UI's freshness affordance,
 *      so an operator can tell at a glance whether the visible numbers
 *      came from the cached aggregate or a fresh one.
 *
 * Real DashboardOverview, real React Query, real Zustand authStore;
 * only the shared apiClient HTTP seam is auto-mocked so the test does
 * not hit a backend.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { DashboardOverview } from './DashboardOverview';

function makeSummary(overrides: Record<string, unknown> = {}) {
  return {
    generated_at: '2026-05-11T10:00:00Z',
    cache_ttl_seconds: 300,
    cache_hit: false,
    tenants: {
      total: 12,
      active: 9,
      suspended: 1,
      deleted: 2,
      legal_hold: 1,
      scheduled_for_deletion: 2,
    },
    webhooks: {
      total: 6,
      active: 4,
      paused: 1,
      disabled: 1,
      delivery_health_last_24h: {
        success: 100,
        failed: 3,
        dead_letter: 1,
        rate_limited: 0,
      },
    },
    audit: {
      events_last_24h: 4567,
      integrity_mismatch_count: 0,
      integrity_verified_at: '2026-05-11T09:55:00Z',
    },
    compliance: {
      pending: 2,
      running: 1,
      succeeded_last_24h: 17,
      failed_last_24h: 1,
    },
    billing: {
      active: 8,
      past_due: 1,
      canceled: 2,
      trial: 1,
      incomplete: 0,
      unpaid: 0,
    },
    governance: {
      open_access_requests: 3,
      approved_access_requests: 12,
      rejected_access_requests: 1,
    },
    ...overrides,
  };
}

describe('DashboardOverview', () => {
  let queryClient: QueryClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  });

  afterEach(() => {
    queryClient.clear();
  });

  it('renders all six widgets with seeded counts', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValueOnce({
      data: makeSummary(),
    } as never);

    render(<DashboardOverview />, { wrapper: Wrapper });

    await waitFor(() =>
      expect(screen.getByTestId('admin-dashboard-overview')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('admin-widget-tenants')).toBeInTheDocument();
    expect(screen.getByTestId('admin-widget-webhooks')).toBeInTheDocument();
    expect(screen.getByTestId('admin-widget-audit')).toBeInTheDocument();
    expect(screen.getByTestId('admin-widget-compliance')).toBeInTheDocument();
    expect(screen.getByTestId('admin-widget-billing')).toBeInTheDocument();
    expect(screen.getByTestId('admin-widget-governance')).toBeInTheDocument();

    // Spot-check that a few of the seeded counts actually appear so a
    // future "decoded but never rendered" regression is caught. We
    // scope each assertion to its widget via ``within(...)`` because
    // raw ``getByText`` matches across the whole dashboard — the
    // seeded fixture deliberately overlaps several integers across
    // widgets (e.g. tenants.total=12 AND governance.approved=12), so
    // an unscoped ``getByText('12')`` would throw the React Testing
    // Library "found multiple elements" error.
    const tenantsCard = screen.getByTestId('admin-widget-tenants');
    expect(within(tenantsCard).getByText('12')).toBeInTheDocument(); // tenants.total
    expect(within(tenantsCard).getByText('9')).toBeInTheDocument();  // tenants.active
    const auditCard = screen.getByTestId('admin-widget-audit');
    expect(within(auditCard).getByText('4567')).toBeInTheDocument(); // audit events
    const webhooksCard = screen.getByTestId('admin-widget-webhooks');
    expect(within(webhooksCard).getByText('100')).toBeInTheDocument(); // deliveries.success
    const complianceCard = screen.getByTestId('admin-widget-compliance');
    expect(within(complianceCard).getByText('17')).toBeInTheDocument(); // succeeded_last_24h
    const billingCard = screen.getByTestId('admin-widget-billing');
    expect(within(billingCard).getByText('8')).toBeInTheDocument(); // billing.active
    const governanceCard = screen.getByTestId('admin-widget-governance');
    expect(within(governanceCard).getByText('3')).toBeInTheDocument(); // open_access_requests
  });

  it('renders the (cached) freshness badge when cache_hit=true', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValueOnce({
      data: makeSummary({ cache_hit: true }),
    } as never);

    render(<DashboardOverview />, { wrapper: Wrapper });

    await waitFor(() =>
      expect(screen.getByTestId('admin-dashboard-overview')).toBeInTheDocument(),
    );
    expect(screen.getByText(/\(cached\)/)).toBeInTheDocument();
  });

  it('renders the (fresh) freshness badge when cache_hit=false', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValueOnce({
      data: makeSummary({ cache_hit: false }),
    } as never);

    render(<DashboardOverview />, { wrapper: Wrapper });

    await waitFor(() =>
      expect(screen.getByTestId('admin-dashboard-overview')).toBeInTheDocument(),
    );
    expect(screen.getByText(/\(fresh\)/)).toBeInTheDocument();
  });

  it('renders an error fallback for a single failed widget while keeping the others intact', async () => {
    /*
     * Phase 235.5 audit-fix Gap 2 — the SPA mirrors the backend's
     * widget-level error isolation contract. When the backend returns
     * ``{"widget_error": true}`` for one widget (e.g. compliance), the
     * SPA must:
     *   1. Render an inline error banner for THAT widget.
     *   2. Keep rendering the other five widgets normally.
     *   3. Preserve the widget's testid so the dashboard grid
     *      contract (six testids present) still holds.
     */
    vi.mocked(apiClient.getClient().get).mockResolvedValueOnce({
      data: makeSummary({ compliance: { widget_error: true } }),
    } as never);

    render(<DashboardOverview />, { wrapper: Wrapper });

    await waitFor(() =>
      expect(screen.getByTestId('admin-dashboard-overview')).toBeInTheDocument(),
    );
    // Failed widget renders the testid + an error banner.
    const failedWidget = screen.getByTestId('admin-widget-compliance');
    expect(failedWidget).toBeInTheDocument();
    expect(within(failedWidget).getByRole('alert')).toBeInTheDocument();
    expect(
      within(failedWidget).getByText(/admin_dashboard_widget_failed/),
    ).toBeInTheDocument();
    // Other five widgets render their normal content.
    expect(screen.getByTestId('admin-widget-tenants')).toBeInTheDocument();
    expect(screen.getByTestId('admin-widget-webhooks')).toBeInTheDocument();
    expect(screen.getByTestId('admin-widget-audit')).toBeInTheDocument();
    expect(screen.getByTestId('admin-widget-billing')).toBeInTheDocument();
    expect(screen.getByTestId('admin-widget-governance')).toBeInTheDocument();
    // The healthy widgets surface their real counters.
    const tenantsCard = screen.getByTestId('admin-widget-tenants');
    expect(within(tenantsCard).getByText('12')).toBeInTheDocument();
  });

  it('renders the Refresh button', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValueOnce({
      data: makeSummary(),
    } as never);

    render(<DashboardOverview />, { wrapper: Wrapper });

    await waitFor(() =>
      expect(screen.getByTestId('admin-dashboard-refresh')).toBeInTheDocument(),
    );
  });
});
