/**
 * Phase 277.B.031 — CpoCostOverviewPage Vitest component tests.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { CpoCostOverviewPage } from '../CpoCostOverviewPage';
import * as apiModule from '../../../../shared/api/client';

const mockGet = vi.fn();

vi.mock('../../../../shared/api/client', () => ({
  apiClient: { getClient: () => ({ get: mockGet }) },
}));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <CpoCostOverviewPage />
    </QueryClientProvider>,
  );
}

const MOCK_DATA = {
  total_cents: 149500,
  currency: 'usd',
  months_included: 12,
  per_tenant: [
    { tenant_id: 'a', tenant_name: 'Acme Corp', total_cents: 75000, order_count: 12 },
  ],
  per_feature: [
    { category: 'marketplace', total_cents: 75000, order_count: 8 },
  ],
  month_over_month: [
    { year: 2026, month: 5, total_cents: 5000, order_count: 1, delta_pct: null },
    { year: 2026, month: 4, total_cents: 8000, order_count: 2, delta_pct: -37.5 },
  ],
};

describe('CpoCostOverviewPage', () => {
  it('shows loading spinner initially', () => {
    mockGet.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText('Loading cost overview...')).toBeDefined();
  });

  it('shows error display on API failure', async () => {
    mockGet.mockRejectedValue(new Error('Network error'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Failed to load cost overview')).toBeDefined();
    });
  });

  it('shows empty state when data is null', async () => {
    mockGet.mockResolvedValue({ data: null });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('No cost data')).toBeDefined();
    });
  });

  it('renders total spend, tenant table, feature table, and MoM trend', async () => {
    mockGet.mockResolvedValue({ data: MOCK_DATA });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('cpo-cost-overview')).toBeDefined();
      expect(screen.getByTestId('cost-total')).toBeDefined();
      expect(screen.getByTestId('cost-tenant-table')).toBeDefined();
      expect(screen.getByTestId('cost-tenant-a')).toBeDefined();
      expect(screen.getByTestId('cost-feature-table')).toBeDefined();
      expect(screen.getByTestId('cost-feature-marketplace')).toBeDefined();
      expect(screen.getByTestId('cost-mom-table')).toBeDefined();
      expect(screen.getByTestId('cost-mom-2026-5')).toBeDefined();
    });
  });

  it('renders empty rows when arrays are empty', async () => {
    mockGet.mockResolvedValue({
      data: { ...MOCK_DATA, per_tenant: [], per_feature: [], month_over_month: [] },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('No tenant data')).toBeDefined();
      expect(screen.getByText('No feature data')).toBeDefined();
      expect(screen.getByText('No monthly data')).toBeDefined();
    });
  });
});
