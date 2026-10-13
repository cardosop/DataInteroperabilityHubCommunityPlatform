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

describe('ErrorBoundary chunk-load recovery', () => {
  function setOnline(online: boolean) {
    Object.defineProperty(window.navigator, 'onLine', {
      value: online,
      configurable: true,
    });
  }

  // jsdom's `location.reload` is a non-configurable own property, so it
  // cannot be spyOn'd directly — replace the whole location object with a
  // stub that only implements reload (the only member the boundary touches).
  function stubLocationReload() {
    const descriptor = Object.getOwnPropertyDescriptor(window, 'location');
    const reload = vi.fn();
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: { reload },
    });
    return {
      reload,
      restore: () => {
        Object.defineProperty(window, 'location', descriptor as PropertyDescriptor);
      },
    };
  }

  afterEach(() => {
    // Drop the own property so the prototype getter is restored.
    Reflect.deleteProperty(window.navigator, 'onLine');
    window.sessionStorage.clear();
  });

  it('reloads once on a chunk-load error while online', () => {
    setOnline(true);
    const { reload, restore } = stubLocationReload();
    try {
      render(
        <ErrorBoundary>
          <ThrowingChild msg="Failed to fetch dynamically imported module" />
        </ErrorBoundary>,
      );
      expect(reload).toHaveBeenCalledTimes(1);
    } finally {
      restore();
    }
  });

  it('does not reload on a chunk-load error while offline — surfaces the error UI instead', () => {
    // The same failure message covers a genuine connectivity error; a
    // reload here would land on the browser's network-error page.
    setOnline(false);
    const { reload, restore } = stubLocationReload();
    try {
      render(
        <ErrorBoundary>
          <ThrowingChild msg="Failed to fetch dynamically imported module" />
        </ErrorBoundary>,
      );
      expect(reload).not.toHaveBeenCalled();
      expect(screen.getByText('Something went wrong')).toBeTruthy();
    } finally {
      restore();
    }
  });

  it('fallback ErrorDisplay offers a Retry button', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild msg="Plain render error" />
      </ErrorBoundary>,
    );
    expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy();
  });
});
