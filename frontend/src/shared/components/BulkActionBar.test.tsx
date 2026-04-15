/**
 * BulkActionBar — 223.3.2 tests.
 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { BulkActionBar } from './BulkActionBar';

describe('BulkActionBar', () => {
  it('does not render when selectedCount is 0', () => {
    const { container } = render(
      <BulkActionBar
        selectedCount={0}
        onDeselectAll={() => {}}
        actions={[{ label: 'Approve', onClick: () => {} }]}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('shows selected count and action buttons', () => {
    render(
      <BulkActionBar
        selectedCount={3}
        onDeselectAll={() => {}}
        actions={[
          { label: 'Approve', onClick: () => {} },
          { label: 'Reject', onClick: () => {}, variant: 'danger' },
        ]}
      />,
    );
    expect(screen.getByTestId('bulk-action-bar')).toHaveTextContent(/3 selected/);
    expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument();
  });

  it('invokes onClick for the right action', async () => {
    const user = userEvent.setup();
    const onApprove = vi.fn();
    const onReject = vi.fn();
    render(
      <BulkActionBar
        selectedCount={1}
        onDeselectAll={() => {}}
        actions={[
          { label: 'Approve', onClick: onApprove },
          { label: 'Reject', onClick: onReject, variant: 'danger' },
        ]}
      />,
    );
    await user.click(screen.getByRole('button', { name: /approve/i }));
    expect(onApprove).toHaveBeenCalledTimes(1);
    expect(onReject).not.toHaveBeenCalled();
  });

  it('deselect button calls onDeselectAll', async () => {
    const user = userEvent.setup();
    const onDeselect = vi.fn();
    render(
      <BulkActionBar
        selectedCount={2}
        onDeselectAll={onDeselect}
        actions={[{ label: 'Approve', onClick: () => {} }]}
      />,
    );
    await user.click(screen.getByRole('button', { name: /clear selection/i }));
    expect(onDeselect).toHaveBeenCalledTimes(1);
  });

  it('respects action `disabled` flag', () => {
    render(
      <BulkActionBar
        selectedCount={1}
        onDeselectAll={() => {}}
        actions={[{ label: 'Delete', onClick: () => {}, disabled: true }]}
      />,
    );
    expect(screen.getByRole('button', { name: /delete/i })).toBeDisabled();
  });
});
