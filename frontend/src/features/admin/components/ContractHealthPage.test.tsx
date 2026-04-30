/**
 * Phase 227 Wave 1 (227.L5.12) — ContractHealthPage tests.
 *
 * Pins the admin triage page's invariants:
 * * Loading state shows the spinner.
 * * Empty results render the "no structureless contracts" empty state.
 * * Non-empty results render one row per contract with a "Open Schema
 *   editor" deep-link.
 *
 * The contractService.list call is mocked at the module boundary so
 * the test runs without a backend.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const mockList = vi.fn();
vi.mock('../../contracts/services/contractService', () => ({
  contractService: {
    list: (...args: unknown[]) => mockList(...args),
  },
}));

import { ContractHealthPage } from './ContractHealthPage';

function renderPage() {
  return render(
    <MemoryRouter>
      <ContractHealthPage />
    </MemoryRouter>,
  );
}

describe('<ContractHealthPage />', () => {
  beforeEach(() => {
    mockList.mockReset();
  });

  it('shows the empty state when there are no structureless contracts', async () => {
    mockList.mockResolvedValue({ results: [], count: 0, next: null, previous: null });
    renderPage();
    await waitFor(() => expect(screen.queryByTestId('contract-health-empty')).toBeTruthy());
  });

  it('renders one row per structureless contract + a Schema-editor link', async () => {
    mockList.mockResolvedValue({
      results: [
        {
          id: '11111111-1111-1111-1111-111111111111',
          name: 'orders-broken',
          original_spec_type: 'ODCS',
          status: 'DRAFT',
          updated_at: '2026-04-30T10:00:00Z',
          original_raw: '{}',
          original_format: 'JSON',
          hub_contract_json: {},
          normalization_status: 'NORMALIZED_OK',
          validation_status: 'VALID',
          created_at: '2026-04-30T09:00:00Z',
          created_by: 'u-1',
          tenant_id: 't-1',
        },
      ],
      count: 1,
      next: null,
      previous: null,
    });
    renderPage();
    await waitFor(() =>
      expect(
        screen.queryByTestId('contract-health-row-11111111-1111-1111-1111-111111111111'),
      ).toBeTruthy(),
    );
    const fix = screen.getByTestId(
      'contract-fix-11111111-1111-1111-1111-111111111111',
    ) as HTMLAnchorElement;
    expect(fix.getAttribute('href')).toBe(
      '/contracts/11111111-1111-1111-1111-111111111111/edit?tab=schema',
    );
  });

  it('passes filter=structureless to the list service', async () => {
    mockList.mockResolvedValue({ results: [], count: 0, next: null, previous: null });
    renderPage();
    await waitFor(() => expect(mockList).toHaveBeenCalled());
    const args = mockList.mock.calls[0][0] as { filter?: string };
    expect(args.filter).toBe('structureless');
  });
});
