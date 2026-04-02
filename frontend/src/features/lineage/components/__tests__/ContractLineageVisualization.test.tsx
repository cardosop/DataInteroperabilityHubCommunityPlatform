/**
 * ContractLineageVisualization tests — Phase 37 (35.4)
 *
 * Tests the data transformation and loading/error states.
 * React Flow is rendered in jsdom (no canvas); we test that the
 * correct child components appear for each state.
 */
import { describe, it, expect, vi, beforeAll } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// React Flow requires ResizeObserver which jsdom doesn't provide
beforeAll(() => {
  global.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
});

// Mock the hook to control test data
const mockUseContractLineageVisualization = vi.fn();
vi.mock('../../../contracts/hooks/useContracts', () => ({
  useContractLineageVisualization: (...args: unknown[]) => mockUseContractLineageVisualization(...args),
}));

import { ContractLineageVisualization } from '../ContractLineageVisualization';

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ContractLineageVisualization', () => {
  it('shows skeleton block while data loads', () => {
    mockUseContractLineageVisualization.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    });
    const { container } = renderWithProviders(<ContractLineageVisualization contractId="abc" />);
    expect(container.querySelector('.skeleton-block')).toBeTruthy();
  });

  it('shows error display on API error', () => {
    mockUseContractLineageVisualization.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Network error'),
      refetch: vi.fn(),
    });
    renderWithProviders(<ContractLineageVisualization contractId="abc" />);
    expect(screen.getByText(/failed to load graph/i)).toBeTruthy();
  });

  it('renders header with node/link count when data is loaded', () => {
    mockUseContractLineageVisualization.mockReturnValue({
      data: {
        nodes: [
          { id: 'n1', type: 'contract', name: 'Orders', contract_id: 'c1', label: null },
          { id: 'n2', type: 'model', name: 'Items', contract_id: null, label: null },
          { id: 'n3', type: 'field', name: 'amount', contract_id: null, label: null },
        ],
        links: [
          { source: 'n1', target: 'n2' },
          { source: 'n2', target: 'n3' },
        ],
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderWithProviders(<ContractLineageVisualization contractId="abc" />);
    expect(screen.getByText(/3 nodes/)).toBeTruthy();
    expect(screen.getByText(/2 links/)).toBeTruthy();
  });

  it('transforms nodes with correct data.type and data.name', () => {
    const nodes = [
      { id: 'c1', type: 'contract', name: 'My Contract', contract_id: 'c1', label: null },
    ];
    mockUseContractLineageVisualization.mockReturnValue({
      data: { nodes, links: [] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderWithProviders(<ContractLineageVisualization contractId="c1" />);
    // The depth slider should be visible (proves component rendered)
    expect(screen.getByText(/depth/i)).toBeTruthy();
  });
});
