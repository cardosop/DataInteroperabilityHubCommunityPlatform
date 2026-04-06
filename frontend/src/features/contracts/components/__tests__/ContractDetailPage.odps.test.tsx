/**
 * Tests for ContractDetailPage — ODPS conditional rendering.
 *
 * TDD: Tests written FIRST for ODPS-specific sections.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ContractDetailPage } from '../ContractDetailPage';
import { ToastProvider } from '../../../../shared/components/Toast';
import { contractService } from '../../services/contractService';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeContract(overrides: Record<string, unknown> = {}) {
  return {
    id: 'c-123',
    name: 'Test Contract',
    original_raw: '{}',
    original_format: 'JSON',
    original_spec_type: undefined,
    hub_contract_json: {},
    normalization_status: 'NORMALIZED_OK',
    validation_status: 'VALID',
    created_at: '2026-04-01T00:00:00Z',
    updated_at: '2026-04-01T00:00:00Z',
    created_by: 'user1',
    tenant_id: 't1',
    ...overrides,
  };
}

function renderDetail(contractOverrides: Record<string, unknown> = {}) {
  const contract = makeContract(contractOverrides);

  vi.spyOn(contractService, 'getById').mockResolvedValue(contract as ReturnType<typeof contractService.getById> extends Promise<infer T> ? T : never);
  vi.spyOn(contractService, 'getLinks').mockResolvedValue({
    odps_link: null,
    odcs_link: null,
  });

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/contracts/${contract.id}`]}>
          <Routes>
            <Route path="/contracts/:id" element={<ContractDetailPage />} />
            <Route path="/contracts/:id/link-odps" element={<div>Link ODPS Page</div>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Generic contracts (no spec_type)
// ---------------------------------------------------------------------------

describe('ContractDetailPage — generic contract', () => {
  it('renders contract name in heading', async () => {
    renderDetail({ name: 'My Contract' });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /my contract/i })).toBeInTheDocument();
    });
  });

  it('does NOT show linked contracts section for non-ODPS contracts', async () => {
    renderDetail({ original_spec_type: undefined });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /test contract/i })).toBeInTheDocument();
    });

    expect(screen.queryByText(/linked contracts/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// ODPS contracts
// ---------------------------------------------------------------------------

describe('ContractDetailPage — ODPS contract', () => {
  it('shows spec type in metadata for ODPS', async () => {
    renderDetail({ original_spec_type: 'ODPS' });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /test contract/i })).toBeInTheDocument();
    });

    // Spec type should appear somewhere in the metadata area
    expect(screen.getByText('ODPS')).toBeInTheDocument();
  });

  it('shows Link ODCS button for ODPS contracts', async () => {
    renderDetail({ original_spec_type: 'ODPS' });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /test contract/i })).toBeInTheDocument();
    });

    // ODPS contracts should have a link button to connect an ODCS contract
    const linkBtn = screen.queryByText(/link odcs/i);
    expect(linkBtn).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// ODCS contracts
// ---------------------------------------------------------------------------

describe('ContractDetailPage — ODCS contract', () => {
  it('shows spec type in metadata for ODCS', async () => {
    renderDetail({ original_spec_type: 'ODCS' });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /test contract/i })).toBeInTheDocument();
    });

    expect(screen.getByText('ODCS')).toBeInTheDocument();
  });

  it('shows Link ODPS button for ODCS contracts', async () => {
    renderDetail({ original_spec_type: 'ODCS' });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /test contract/i })).toBeInTheDocument();
    });

    // Already exists in the current implementation (line 118)
    const linkBtn = screen.queryByText(/link odps/i);
    expect(linkBtn).toBeInTheDocument();
  });
});
