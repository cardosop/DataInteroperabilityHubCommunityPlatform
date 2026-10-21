/**
 * ConfirmDialog Component Tests
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ConfirmDialog } from '../ConfirmDialog';

describe('ConfirmDialog', () => {
  it('renders nothing when isOpen is false', () => {
    render(
      <ConfirmDialog
        isOpen={false}
        onClose={() => {}}
        onConfirm={() => {}}
        title="Confirm"
        message="Are you sure?"
      />
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders dialog with title and message when isOpen', () => {
    render(
      <ConfirmDialog
        isOpen
        onClose={() => {}}
        onConfirm={() => {}}
        title="Delete Dataset"
        message="Are you sure you want to delete this dataset?"
      />
    );
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Delete Dataset')).toBeInTheDocument();
    expect(screen.getByText('Are you sure you want to delete this dataset?')).toBeInTheDocument();
  });

  it('calls onClose when Cancel is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <ConfirmDialog
        isOpen
        onClose={onClose}
        onConfirm={() => {}}
        title="Confirm"
        message="Message"
      />
    );
    await user.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onConfirm when Confirm is clicked', async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    render(
      <ConfirmDialog
        isOpen
        onClose={() => {}}
        onConfirm={onConfirm}
        title="Confirm"
        message="Message"
      />
    );
    await user.click(screen.getByRole('button', { name: /confirm|delete|yes/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('uses custom confirm and cancel labels', () => {
    render(
      <ConfirmDialog
        isOpen
        onClose={() => {}}
        onConfirm={() => {}}
        title="Confirm"
        message="Message"
        confirmLabel="Delete"
        cancelLabel="Keep"
      />
    );
    expect(screen.getByRole('button', { name: /keep/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
  });

  it('calls onClose when Escape key is pressed', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <ConfirmDialog
        isOpen
        onClose={onClose}
        onConfirm={() => {}}
        title="Confirm"
        message="Message"
      />
    );
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('traps focus within dialog when open', () => {
    render(
      <ConfirmDialog
        isOpen
        onClose={() => {}}
        onConfirm={() => {}}
        title="Confirm"
        message="Message"
      />
    );
    const dialog = screen.getByRole('dialog');
    const cancelBtn = screen.getByRole('button', { name: /cancel/i });
    const confirmBtn = screen.getByRole('button', { name: /confirm/i });
    const closeBtn = screen.getByRole('button', { name: /close dialog/i });
    expect(dialog).toBeInTheDocument();
    expect(cancelBtn).toBeInTheDocument();
    expect(confirmBtn).toBeInTheDocument();
    expect(closeBtn).toBeInTheDocument();
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it('applies danger variant styling when variant is danger', () => {
    render(
      <ConfirmDialog
        isOpen
        onClose={() => {}}
        onConfirm={() => {}}
        title="Delete"
        message="This cannot be undone."
        confirmLabel="Delete"
        variant="danger"
      />
    );
    const body = document.querySelector('.confirm-dialog-body');
    expect(body).toHaveClass('confirm-dialog-danger');
  });
});
