/**
 * Phase 85.5 — FeatureErrorBoundary tests.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FeatureErrorBoundary } from '../FeatureErrorBoundary';

function ThrowingChild({ msg = 'boom' }: { msg?: string }) {
  throw new Error(msg);
}

describe('FeatureErrorBoundary', () => {
  // Suppress console.error from React error boundary
  const origError = console.error;
  beforeEach(() => { console.error = vi.fn(); });
  afterEach(() => { console.error = origError; });

  it('renders children when no error', () => {
    render(
      <FeatureErrorBoundary feature="Test">
        <p>OK</p>
      </FeatureErrorBoundary>,
    );
    expect(screen.getByText('OK')).toBeTruthy();
  });

  it('catches render error and shows fallback', () => {
    render(
      <FeatureErrorBoundary feature="Dashboard">
        <ThrowingChild />
      </FeatureErrorBoundary>,
    );
    expect(screen.getByTestId('feature-error-boundary-fallback')).toBeTruthy();
  });

  it('shows feature name in fallback', () => {
    render(
      <FeatureErrorBoundary feature="Contracts">
        <ThrowingChild />
      </FeatureErrorBoundary>,
    );
    expect(screen.getByText(/Contracts/)).toBeTruthy();
  });

  it('shows error message in fallback', () => {
    render(
      <FeatureErrorBoundary feature="X">
        <ThrowingChild msg="custom error text" />
      </FeatureErrorBoundary>,
    );
    expect(screen.getByText('custom error text')).toBeTruthy();
  });

  it('retry resets error state and re-renders children', () => {
    let shouldThrow = true;
    function Conditional() {
      if (shouldThrow) throw new Error('first');
      return <p>Recovered</p>;
    }

    render(
      <FeatureErrorBoundary feature="X">
        <Conditional />
      </FeatureErrorBoundary>,
    );
    expect(screen.getByTestId('feature-error-boundary-fallback')).toBeTruthy();

    shouldThrow = false;
    fireEvent.click(screen.getByTestId('feature-error-boundary-retry'));
    expect(screen.getByText('Recovered')).toBeTruthy();
  });
});
