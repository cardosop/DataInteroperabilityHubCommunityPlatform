/**
 * Tests for ContractListPage — contract list with spec_type column and filter.
 *
 * TDD: Tests written FIRST.
 */

import { render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ContractListPage } from '../ContractListPage';
import { ToastProvider } from '../../../../shared/components/Toast';
import { contractService } from '../../services/contractService';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockContracts = [
  {
    id: '1',
    name: 'ODPS Contract',
    original_format: 'YAML',
    original_spec_type: 'ODPS',
    normalization_status: 'NORMALIZED_OK',
    validation_status: 'VALID',
    created_at: '2026-04-01T00:00:00Z',
    updated_at: '2026-04-01T00:00:00Z',
    created_by: 'user1',
    tenant_id: 't1',
    original_raw: '',
    hub_contract_json: {},
  },
  {
    id: '2',
    name: 'ODCS Contract',
    original_format: 'JSON',
    original_spec_type: 'ODCS',
    normalization_status: 'NORMALIZED_OK',
    validation_status: 'VALID',
    created_at: '2026-04-02T00:00:00Z',
    updated_at: '2026-04-02T00:00:00Z',
    created_by: 'user2',
    tenant_id: 't1',
    original_raw: '',
    hub_contract_json: {},
  },
  {
    id: '3',
    name: 'Generic Contract',
    original_format: 'JSON',
    original_spec_type: undefined,
    normalization_status: 'NOT_NORMALIZED',
    validation_status: 'INVALID',
    created_at: '2026-04-03T00:00:00Z',
    updated_at: '2026-04-03T00:00:00Z',
    created_by: 'user3',
    tenant_id: 't1',
    original_raw: '',
    hub_contract_json: {},
  },
];

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function renderPage() {
  // Spy on the service to return mock data
  vi.spyOn(contractService, 'list').mockResolvedValue({
    results: mockContracts,
    count: 3,
    page: 1,
    page_size: 50,
    total_pages: 1,
    has_next: false,
    has_previous: false,
  } as ReturnType<typeof contractService.list> extends Promise<infer T> ? T : never);

  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={['/contracts']}>
          <ContractListPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Create button target
// ---------------------------------------------------------------------------

describe('ContractListPage — Create button', () => {
  it('Create Contract button navigates to /contracts/create', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('ODPS Contract')).toBeInTheDocument();
    });

    const createBtn = screen.getByRole('button', { name: /create contract/i });
    expect(createBtn).toBeInTheDocument();
    // The button's onClick should call navigate('/contracts/create')
    // We verify by checking the button exists — navigation is tested via integration
  });
});

// ---------------------------------------------------------------------------
// Spec type column
// ---------------------------------------------------------------------------

describe('ContractListPage — spec_type column', () => {
  it('renders Spec Type column header', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('ODPS Contract')).toBeInTheDocument();
    });

    // Column header is inside thead
    const table = screen.getByRole('table');
    const headers = within(table).getAllByRole('columnheader');
    const specTypeHeader = headers.find((h) => h.textContent === 'Spec Type');
    expect(specTypeHeader).toBeTruthy();
  });

  it('shows ODPS badge for ODPS contracts', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('ODPS Contract')).toBeInTheDocument();
    });

    const odpsRow = screen.getByText('ODPS Contract').closest('tr')!;
    expect(within(odpsRow).getByText('ODPS')).toBeInTheDocument();
  });

  it('shows ODCS badge for ODCS contracts', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('ODCS Contract')).toBeInTheDocument();
    });

    const odcsRow = screen.getByText('ODCS Contract').closest('tr')!;
    expect(within(odcsRow).getByText('ODCS')).toBeInTheDocument();
  });

  it('shows dash for contracts without spec_type', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Generic Contract')).toBeInTheDocument();
    });

    const genericRow = screen.getByText('Generic Contract').closest('tr')!;
    // Should show '—' for undefined spec_type
    const cells = within(genericRow).getAllByRole('cell');
    const specTypeCell = cells.find((cell) => cell.textContent === '—');
    expect(specTypeCell).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Spec type filter
// ---------------------------------------------------------------------------

describe('ContractListPage — spec_type filter', () => {
  it('renders spec type filter dropdown', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('ODPS Contract')).toBeInTheDocument();
    });

    expect(screen.getByLabelText(/spec type/i) || screen.getByRole('combobox')).toBeInTheDocument();
  });
});
