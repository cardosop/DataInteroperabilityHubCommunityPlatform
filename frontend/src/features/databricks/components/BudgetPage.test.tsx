/**
 * BudgetPage tests (openspec add-databricks-cost-guardrails task 7.6) —
 * the U9 budget page surface (design D5, the spec's "The budget page
 * shows the progress bar" scenario).
 *
 * UI contract pins:
 *  - a tenant with a budget of 100 units/hour and 60 consumed renders a
 *    progress bar at 60% (aria-valuenow) with the numeric label,
 *  - the per-warehouse breakdown renders each warehouse's rolling-hour
 *    units (the unattributed rows render the null entry),
 *  - an over-budget row clamps the BAR at 100% but the visible
 *    percentage never lies (the raw percent text),
 *  - an unlimited budget row renders without a progress bar,
 *  - a failed load renders the machine-readable CODE in the alert,
 *  - a 403 DATABRICKS_CONTROL_PLANE_DISABLED renders the flag banner,
 *  - the empty state renders with zero rows.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { DatabricksApiError, listBudgets } from '../services/budgetService';
import { BudgetPage } from './BudgetPage';

vi.mock('../services/budgetService', () => ({
  DatabricksApiError: class extends Error {
    code?: string;
    constructor(message: string, code?: string) {
      super(message);
      this.code = code;
    }
  },
  listBudgets: vi.fn(),
}));

const mockListBudgets = vi.mocked(listBudgets);

const ROW = {
  id: 'budget-1',
  warehouse_id: null,
  warehouse_name: null,
  budget_units_per_hour: '100.000000',
  enforcement_mode: 'BLOCK',
  consumed: '60',
  ratio: 0.6,
  percent: 60.0,
  window_seconds: 3600,
  breakdown: [
    { warehouse_id: 'wh-analytics', warehouse_name: 'Analytics', units: '40.000000' },
    { warehouse_id: 'wh-bi', warehouse_name: 'BI', units: '20.000000' },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('BudgetPage', () => {
  it('renders the progress bar at 60% for budget 100 / consumed 60', async () => {
    mockListBudgets.mockResolvedValue([ROW]);
    render(<BudgetPage />);

    await waitFor(() =>
      expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '60')
    );
    expect(screen.getByText('60%')).toBeInTheDocument();
    expect(screen.getByText(/100\.0/)).toBeInTheDocument();
  });

  it('renders the per-warehouse breakdown rows', async () => {
    mockListBudgets.mockResolvedValue([ROW]);
    render(<BudgetPage />);

    const breakdown = await screen.findByRole('list');
    expect(breakdown).toHaveTextContent('Analytics: 40.0');
    expect(breakdown).toHaveTextContent('BI: 20.0');
  });

  it('clamps the bar at 100% for an over-budget row but shows the raw percent', async () => {
    mockListBudgets.mockResolvedValue([
      { ...ROW, consumed: '120', ratio: 1.2, percent: 120.0 },
    ]);
    render(<BudgetPage />);

    await waitFor(() =>
      expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
    );
    expect(screen.getByText('120%')).toBeInTheDocument();
    expect(screen.getByRole('progressbar').closest('.budget-row')).toHaveClass('over-budget');
  });

  it('renders an unlimited budget row without a progress bar', async () => {
    mockListBudgets.mockResolvedValue([
      {
        ...ROW,
        budget_units_per_hour: null,
        ratio: null,
        percent: null,
        consumed: '12',
      },
    ]);
    render(<BudgetPage />);

    expect(await screen.findByText('Unlimited')).toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('renders the machine-readable CODE on a failed load', async () => {
    mockListBudgets.mockRejectedValue(
      new DatabricksApiError('Budget read failed', 'BUDGET_READ_FAILED')
    );
    render(<BudgetPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('[BUDGET_READ_FAILED]');
  });

  it('renders the flag banner on 403 DATABRICKS_CONTROL_PLANE_DISABLED', async () => {
    mockListBudgets.mockRejectedValue(
      new DatabricksApiError('Control plane disabled', 'DATABRICKS_CONTROL_PLANE_DISABLED')
    );
    render(<BudgetPage />);

    expect(await screen.findByTestId('flag-disabled-banner')).toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('renders the empty state with zero rows', async () => {
    mockListBudgets.mockResolvedValue([]);
    render(<BudgetPage />);

    expect(
      await screen.findByText('No cost budgets configured yet.')
    ).toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });
});
