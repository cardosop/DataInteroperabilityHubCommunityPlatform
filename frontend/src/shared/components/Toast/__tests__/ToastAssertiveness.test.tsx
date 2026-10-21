/**
 * Assertive error-toast pins — W5.4 (R2-F5).
 *
 * Pre-fix every toast (including errors) announced with role="status"
 * aria-live="polite": screen readers queue error announcements behind
 * mundane chatter, and the 4s auto-dismiss raced slow readers. Error
 * toasts must be assertive and linger longer than success/info.
 */

import { act, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../ToastContext';
import { useToast } from '../useToast';

function TestConsumer({ type }: { type: 'success' | 'error' | 'info' }) {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast[type]('Message body')}>
      Show {type}
    </button>
  );
}

function renderAndFire(type: 'success' | 'error' | 'info') {
  render(
    <ToastProvider>
      <TestConsumer type={type} />
    </ToastProvider>,
  );
  act(() => {
    fireEvent.click(screen.getByRole('button', { name: new RegExp(`show ${type}`, 'i') }));
  });
}

describe('Toast assertiveness', () => {
  it('announces ERROR toasts assertively (role=alert, aria-live=assertive)', () => {
    renderAndFire('error');

    const toast = screen.getByTestId('toast');
    expect(toast).toHaveAttribute('role', 'alert');
    expect(toast).toHaveAttribute('aria-live', 'assertive');
  });

  it('keeps SUCCESS toasts polite (regression pin)', () => {
    renderAndFire('success');

    const toast = screen.getByTestId('toast');
    expect(toast).toHaveAttribute('role', 'status');
    expect(toast).toHaveAttribute('aria-live', 'polite');
  });

  it('keeps INFO toasts polite (regression pin)', () => {
    renderAndFire('info');

    const toast = screen.getByTestId('toast');
    expect(toast).toHaveAttribute('role', 'status');
    expect(toast).toHaveAttribute('aria-live', 'polite');
  });

  it('keeps error toasts visible longer than the 4s default', () => {
    vi.useFakeTimers();
    renderAndFire('error');

    act(() => {
      vi.advanceTimersByTime(4000);
    });
    // Success/info would be gone by now; errors must still be announced.
    expect(screen.getByTestId('toast')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.queryByTestId('toast')).not.toBeInTheDocument();

    vi.useRealTimers();
  });

  it('keeps success toasts at the 4s default (regression pin)', () => {
    vi.useFakeTimers();
    renderAndFire('success');

    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.queryByTestId('toast')).not.toBeInTheDocument();

    vi.useRealTimers();
  });
});
