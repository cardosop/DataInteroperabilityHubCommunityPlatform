/**
 * Toast Component Tests
 */

import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ToastProvider, useToast } from '../ToastContext';

function TestConsumerSuccess() {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast.success('Asset created successfully')}>
      Show Success
    </button>
  );
}

function TestConsumerError() {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast.error('Something went wrong')}>
      Show Error
    </button>
  );
}

function TestConsumerInfo() {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast.info('Processing...')}>
      Show Info
    </button>
  );
}

describe('Toast', () => {
  it('shows success toast when toast.success is called', async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <TestConsumerSuccess />
      </ToastProvider>
    );

    await user.click(screen.getByRole('button', { name: /show success/i }));

    expect(screen.getByText('Asset created successfully')).toBeInTheDocument();
    expect(screen.getByTestId('toast')).toHaveClass('toast-success');
  });

  it('shows error toast when toast.error is called', async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <TestConsumerError />
      </ToastProvider>
    );

    await user.click(screen.getByRole('button', { name: /show error/i }));

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByTestId('toast')).toHaveClass('toast-error');
  });

  it('shows info toast when toast.info is called', async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <TestConsumerInfo />
      </ToastProvider>
    );

    await user.click(screen.getByRole('button', { name: /show info/i }));

    expect(screen.getByText('Processing...')).toBeInTheDocument();
    expect(screen.getByTestId('toast')).toHaveClass('toast-info');
  });

  it('auto-dismisses toast after duration', () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <TestConsumerSuccess />
      </ToastProvider>
    );

    act(() => {
      fireEvent.click(screen.getByRole('button', { name: /show success/i }));
    });
    expect(screen.getByText('Asset created successfully')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.queryByText('Asset created successfully')).not.toBeInTheDocument();

    vi.useRealTimers();
  });

  it('useToast throws when used outside provider', () => {
    expect(() => {
      render(
        <div>
          <TestConsumerSuccess />
        </div>
      );
    }).toThrow('useToast must be used within ToastProvider');
  });
});
