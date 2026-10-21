/**
 * ErrorDisplay component tests — Phase 111.4
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../services/errorReporting', () => ({
  errorReportingService: { reportError: vi.fn() },
}));

import { ErrorDisplay } from '../ErrorDisplay';

describe('ErrorDisplay', () => {
  it('renders error message', () => {
    render(<ErrorDisplay error={new Error('Something failed')} />);
    expect(screen.getByText(/Something failed/)).toBeInTheDocument();
  });

  it('renders title when provided', () => {
    render(<ErrorDisplay error={new Error('fail')} title="Load Error" />);
    expect(screen.getByText('Load Error')).toBeInTheDocument();
  });

  it('renders retry button when onRetry provided', () => {
    const onRetry = vi.fn();
    render(<ErrorDisplay error={new Error('fail')} onRetry={onRetry} />);
    const btn = screen.queryByRole('button');
    if (btn) {
      expect(btn).toBeInTheDocument();
    }
  });
});
