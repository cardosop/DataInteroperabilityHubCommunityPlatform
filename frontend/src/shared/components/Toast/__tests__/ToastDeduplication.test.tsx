/**
 * Toast Deduplication Tests — Phase 41
 */

import { render, screen, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { ToastProvider } from '../ToastContext';
import { useToast } from '../useToast';

/** Helper component that exposes toast methods via buttons */
function ToastTrigger() {
  const toast = useToast();
  return (
    <div>
      <button onClick={() => toast.success('Saved')}>fire</button>
    </div>
  );
}

describe('Toast deduplication', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  it('two identical toasts within 500ms show only one', () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    );

    const btn = screen.getByText('fire');

    // Fire twice rapidly (0ms gap)
    act(() => { btn.click(); });
    act(() => { btn.click(); });

    const toasts = screen.getAllByTestId('toast');
    expect(toasts).toHaveLength(1);

    vi.useRealTimers();
  });

  it('two identical toasts 600ms apart both appear', () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    );

    const btn = screen.getByText('fire');

    act(() => { btn.click(); });

    // Advance past the dedup window
    act(() => { vi.advanceTimersByTime(600); });

    act(() => { btn.click(); });

    const toasts = screen.getAllByTestId('toast');
    expect(toasts).toHaveLength(2);

    vi.useRealTimers();
  });
});
