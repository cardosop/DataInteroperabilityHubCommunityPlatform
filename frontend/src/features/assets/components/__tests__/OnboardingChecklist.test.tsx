/**
 * Tests for OnboardingChecklist — action buttons for DQ and compliance runs.
 * TDD: Tests written FIRST.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { OnboardingChecklist } from '../OnboardingChecklist';
import { ToastProvider } from '../../../../shared/components/Toast';

function renderChecklist(props: Partial<React.ComponentProps<typeof OnboardingChecklist>> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <OnboardingChecklist
            contracts={[]}
            datasets={[]}
            dqStatus=""
            complianceStatus=""
            assetId="asset-123"
            onRunDQ={vi.fn()}
            onRunCompliance={vi.fn()}
            {...props}
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const mockDataset = {
  id: 'ds-1', name: 'Test', format: 'CSV', created_at: '2026-01-01',
  updated_at: '2026-01-01', created_by: 'user', tenant_id: 't1',
};

describe('OnboardingChecklist — DQ action button', () => {
  it('shows "Run DQ Check" button when dataset exists and DQ not passed', () => {
    renderChecklist({
      datasets: [mockDataset as never],
      dqStatus: '',
    });
    expect(screen.getByText(/run dq/i)).toBeInTheDocument();
  });

  it('does NOT show "Run DQ Check" when DQ already passed', () => {
    renderChecklist({
      datasets: [mockDataset as never],
      dqStatus: 'PASSED',
    });
    expect(screen.queryByText(/run dq/i)).not.toBeInTheDocument();
  });

  it('does NOT show "Run DQ Check" when no dataset', () => {
    renderChecklist({
      datasets: [],
      dqStatus: '',
    });
    expect(screen.queryByText(/run dq/i)).not.toBeInTheDocument();
  });
});

describe('OnboardingChecklist — Compliance action button', () => {
  it('shows "Run Compliance" button when dataset exists and compliance not passed', () => {
    renderChecklist({
      datasets: [mockDataset as never],
      complianceStatus: '',
    });
    expect(screen.getByText(/run compliance/i)).toBeInTheDocument();
  });

  it('does NOT show "Run Compliance" when compliance already passed', () => {
    renderChecklist({
      datasets: [mockDataset as never],
      complianceStatus: 'COMPLIANT',
    });
    expect(screen.queryByText(/run compliance/i)).not.toBeInTheDocument();
  });
});
