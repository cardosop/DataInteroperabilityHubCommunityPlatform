/**
 * Phase 94.5 — ErrorBoundary route-level tests.
 * Verifies that ErrorBoundary catches errors in wrapped child components
 * and displays the ErrorDisplay fallback UI.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { ErrorBoundary } from '../ErrorBoundary';

// Mock errorReportingService to avoid side-effects
vi.mock('../../services/errorReporting', () => ({
  errorReportingService: {
    reportError: vi.fn(),
  },
}));

function ThrowingChild({ msg = 'Test render error' }: { msg?: string }) {
  throw new Error(msg);
}

describe('ErrorBoundary', () => {
  const origError = console.error;
  beforeEach(() => {
    console.error = vi.fn();
  });
  afterEach(() => {
    console.error = origError;
  });

  it('renders children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <p>Child content</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText('Child content')).toBeTruthy();
  });

  it('catches render error and displays ErrorDisplay fallback', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild msg="Simulated crash in AssetDetailPage" />
      </ErrorBoundary>,
    );
    // ErrorDisplay renders the error title
    expect(screen.getByText('Something went wrong')).toBeTruthy();
  });

  it('displays the error message in the fallback', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild msg="Component failed to render" />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/Component failed to render/)).toBeTruthy();
  });

  it('renders custom fallback when provided', () => {
    render(
      <ErrorBoundary fallback={<div data-testid="custom-fallback">Custom error UI</div>}>
        <ThrowingChild />
      </ErrorBoundary>,
    );
    expect(screen.getByTestId('custom-fallback')).toBeTruthy();
    expect(screen.getByText('Custom error UI')).toBeTruthy();
  });

  it('reports the error via errorReportingService', async () => {
    const { errorReportingService } = await import('../../services/errorReporting');
    render(
      <ErrorBoundary>
        <ThrowingChild msg="reported error" />
      </ErrorBoundary>,
    );
    expect(errorReportingService.reportError).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'reported error' }),
      expect.objectContaining({ componentStack: expect.any(String) }),
    );
  });
});
