/**
 * TopologyVisualization tests — Phase 38 (36.5)
 *
 * Tests data transformation, loading/error states, EmptyState, and summary rendering.
 * Also tests DomainNode healthColor mapping for token-based colour references.
 * React Flow is rendered in jsdom (no canvas); we verify child components
 * appear for each state.
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
const mockUseMeshTopology = vi.fn();
vi.mock('../../hooks/useMesh', () => ({
  useMeshTopology: (...args: unknown[]) => mockUseMeshTopology(...args),
}));

import { TopologyVisualization } from '../TopologyVisualization';
import { healthColor } from '../../constants/healthThresholds';

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

const EMPTY_TOPOLOGY = {
  nodes: [],
  edges: [],
  metadata: { tenant_id: 't1', domain_count: 0, relationship_count: 0, generated_at: '2026-01-01' },
  summary: { total_domains: 0, active_domains: 0, total_relationships: 0 },
};

const FULL_TOPOLOGY = {
  nodes: [
    { id: 'd1', name: 'Sales', status: 'ACTIVE', health_metrics: { health_score: 90, policy_count: 2, compliance_status: 'compliant', violation_count: 0, is_active: true } },
    { id: 'd2', name: 'Marketing', status: 'ACTIVE', health_metrics: { health_score: 70, policy_count: 1, compliance_status: 'warning', violation_count: 1, is_active: true } },
    { id: 'd3', name: 'Finance', status: 'INACTIVE', health_metrics: { health_score: 50, policy_count: 0, compliance_status: 'critical', violation_count: 3, is_active: false } },
  ],
  edges: [
    { source: 'd1', target: 'd2', type: 'data_dependency', weight: 1 },
    { source: 'd2', target: 'd3', type: 'shared_schema', weight: 2 },
  ],
  metadata: { tenant_id: 't1', domain_count: 3, relationship_count: 2, generated_at: '2026-01-01' },
  summary: { total_domains: 3, active_domains: 2, total_relationships: 2, average_health_score: 70 },
};

describe('TopologyVisualization', () => {
  it('shows skeleton block while data loads', () => {
    mockUseMeshTopology.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    });
    const { container } = renderWithProviders(<TopologyVisualization />);
    expect(container.querySelector('.skeleton-block')).toBeTruthy();
  });

  it('shows error display on API error', () => {
    mockUseMeshTopology.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Network error'),
      refetch: vi.fn(),
    });
    renderWithProviders(<TopologyVisualization />);
    expect(screen.getByText(/failed to load graph/i)).toBeTruthy();
  });

  it('renders EmptyState when topology has zero nodes', () => {
    mockUseMeshTopology.mockReturnValue({
      data: EMPTY_TOPOLOGY,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderWithProviders(<TopologyVisualization />);
    expect(screen.getByText('No domains found')).toBeTruthy();
    expect(screen.getByText('Create a data mesh domain to see the topology.')).toBeTruthy();
    expect(screen.getByTestId('topology-empty-state')).toBeTruthy();
  });

  it('renders React Flow canvas when topology has 3 nodes and 2 edges', () => {
    mockUseMeshTopology.mockReturnValue({
      data: FULL_TOPOLOGY,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    const { container } = renderWithProviders(<TopologyVisualization />);
    // React Flow renders a div with class "react-flow"
    expect(container.querySelector('.react-flow')).toBeTruthy();
    // Summary should show 3 domains and 2 relationships
    expect(screen.getByText(/3 Domains/)).toBeTruthy();
    expect(screen.getByText(/2 Relationships/)).toBeTruthy();
  });

  it('renders header with avg health when data is loaded', () => {
    mockUseMeshTopology.mockReturnValue({
      data: FULL_TOPOLOGY,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderWithProviders(<TopologyVisualization />);
    expect(screen.getByText(/Avg Health: 70.0/)).toBeTruthy();
  });

  it('calls useMeshTopology with includeHealthMetrics=true', () => {
    mockUseMeshTopology.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    });
    renderWithProviders(<TopologyVisualization />);
    expect(mockUseMeshTopology).toHaveBeenCalledWith(true);
  });

  it('renders legend with threshold values', () => {
    mockUseMeshTopology.mockReturnValue({
      data: EMPTY_TOPOLOGY,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderWithProviders(<TopologyVisualization />);
    expect(screen.getByText(/Legend/)).toBeTruthy();
    expect(screen.getByText(/≥ 80/)).toBeTruthy();
    expect(screen.getByText(/< 60/)).toBeTruthy();
  });
});

describe('DomainNode healthColor', () => {
  it('health_score=85 returns success-colour token', () => {
    const color = healthColor(85);
    expect(color).toContain('--color-success-500');
    expect(color).toContain('#4CAF50');
  });

  it('health_score=80 (boundary) returns success-colour token', () => {
    const color = healthColor(80);
    expect(color).toContain('--color-success-500');
  });

  it('health_score=70 returns warning-colour token', () => {
    const color = healthColor(70);
    expect(color).toContain('--color-warning-500');
    expect(color).toContain('#FFC107');
  });

  it('health_score=55 returns error-colour token', () => {
    const color = healthColor(55);
    expect(color).toContain('--color-error-500');
    expect(color).toContain('#F44336');
  });

  it('health_score=60 (boundary) returns warning-colour token', () => {
    const color = healthColor(60);
    expect(color).toContain('--color-warning-500');
  });

  it('health_score=undefined returns neutral-colour token', () => {
    const color = healthColor(undefined);
    expect(color).toContain('--color-neutral-500');
  });
});
