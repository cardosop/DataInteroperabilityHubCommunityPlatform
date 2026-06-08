/**
 * Phase 231.3 — ComplianceBadge (discovery / REQ-COMP-DISCO-001).
 */

import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ErrorBoundary } from '../../../../shared/components/ErrorBoundary';
import { ComplianceBadge } from '../ComplianceBadge';
import { riskDisplayLabel } from '../complianceBadgeUtils';

const baseSummary = {
  id: '00000000-0000-0000-0000-000000000001',
  status: 'SUCCEEDED',
  created_at: '2026-01-01T00:00:00Z',
};

describe('ComplianceBadge', () => {
  it('renders nothing when summary is absent', () => {
    const { container } = render(<ComplianceBadge summary={null} />);
    expect(container.textContent).toBe('');
  });

  it.each([
    ['NONE', 'None risk'],
    ['LOW', 'Low risk'],
    ['MEDIUM', 'Medium risk'],
    ['HIGH', 'High risk'],
    ['CRITICAL', 'Critical risk'],
    ['UNKNOWN', 'Unknown risk'],
  ])('risk pill %s has ARIA label %s (231.3.AUDIT.3)', (level, expectedAria) => {
    render(<ComplianceBadge summary={{ ...baseSummary, risk_level: level }} />);
    expect(screen.getByLabelText(expectedAria)).toBeInTheDocument();
  });

  it('shows regulation highlights when summaries is a non-empty array', () => {
    render(
      <ComplianceBadge
        summary={{
          ...baseSummary,
          risk_level: 'LOW',
          regulation_summaries: ['GDPR Art. 6'],
        }}
      />,
    );
    expect(screen.getByLabelText('Regulation highlights')).toHaveTextContent('GDPR');
  });

  it('error boundary surfaces when regulation_summaries is malformed (231.3.AUDIT.2)', () => {
    // React surfaces caught render errors through console.error in dev,
    // even when an ErrorBoundary handles them. Silence the expected
    // log so it doesn't pollute the test output, while still asserting
    // the boundary renders the fallback (the actual contract).
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      render(
        <ErrorBoundary fallback={<div data-testid="compliance-fallback">Compliance status unavailable</div>}>
          <ComplianceBadge
            summary={{
              ...baseSummary,
              risk_level: 'MEDIUM',
              regulation_summaries: { not: 'an array' },
            }}
          />
        </ErrorBoundary>,
      );
      expect(screen.getByTestId('compliance-fallback')).toHaveTextContent('Compliance status unavailable');
    } finally {
      consoleErrorSpy.mockRestore();
    }
  });
});

describe('riskDisplayLabel', () => {
  it('maps null to Unknown', () => {
    expect(riskDisplayLabel(null)).toBe('Unknown');
  });
});
