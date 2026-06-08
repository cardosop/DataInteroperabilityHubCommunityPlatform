/**
 * DatasetRetireConfirmModal tests — Phase 260.4.A.2.
 *
 * Behavioural tests for the confirmation modal customers see before
 * retiring a dataset. Pass-2 P2-1 mandates: explicit consequences
 * copy + "I understand" checkbox; the Retire CTA is disabled until
 * the checkbox is ticked.
 *
 * Real React render via ``@testing-library/react``; no mocks beyond
 * the parent's onConfirm/onCancel handlers (those are how the
 * component is wired into the surrounding mutation flow).
 *
 * Engineering invariants under test:
 *   - Open + close lifecycle controlled via ``open`` + ``onCancel``.
 *   - Retire CTA ``disabled`` until "I understand" is checked.
 *   - ``onConfirm`` fires with no args when CTA clicked.
 *   - ``onCancel`` fires when Cancel clicked OR Esc pressed.
 *   - Consequences copy mentions: irreversibility, retention window,
 *     hard-deletion. (Resilient regex matches; resilient to copy
 *     tweaks.)
 *   - ARIA: ``role="dialog"`` + ``aria-modal="true"`` + headline
 *     associated via ``aria-labelledby``.
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { DatasetRetireConfirmModal } from './DatasetRetireConfirmModal';

function defaultProps(overrides: Partial<React.ComponentProps<typeof DatasetRetireConfirmModal>> = {}) {
  return {
    open: true,
    datasetName: 'sales-2026.csv',
    retentionDays: 90,
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
    isPending: false,
    ...overrides,
  };
}

describe('DatasetRetireConfirmModal', () => {
  it('renders nothing when open=false', () => {
    const { container } = render(<DatasetRetireConfirmModal {...defaultProps({ open: false })} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders dialog with role + aria-modal + labelledby when open=true', () => {
    render(<DatasetRetireConfirmModal {...defaultProps()} />);
    const dialog = screen.getByTestId('dataset-retire-confirm-modal');
    expect(dialog).toHaveAttribute('role', 'dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby');
  });

  it('shows the dataset name and the consequences copy (irreversible, retention, hard-delete)', () => {
    render(<DatasetRetireConfirmModal {...defaultProps()} />);
    const dialog = screen.getByTestId('dataset-retire-confirm-modal');
    expect(dialog.textContent).toContain('sales-2026.csv');
    expect(dialog.textContent).toMatch(/cannot be undone|irreversibl|permanent/i);
    expect(dialog.textContent).toMatch(/90\s*day/);
    expect(dialog.textContent).toMatch(/hard.?delet|permanently delet/i);
  });

  it('Retire button is disabled until the "I understand" checkbox is ticked', async () => {
    const user = userEvent.setup();
    render(<DatasetRetireConfirmModal {...defaultProps()} />);

    const cta = screen.getByTestId('dataset-retire-confirm-cta');
    expect(cta).toBeDisabled();

    const acknowledge = screen.getByTestId('dataset-retire-confirm-acknowledge');
    await user.click(acknowledge);
    expect(cta).toBeEnabled();
  });

  it('Retire button calls onConfirm when clicked after acknowledgement', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<DatasetRetireConfirmModal {...defaultProps({ onConfirm })} />);
    await user.click(screen.getByTestId('dataset-retire-confirm-acknowledge'));
    await user.click(screen.getByTestId('dataset-retire-confirm-cta'));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('Cancel button calls onCancel and never onConfirm', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<DatasetRetireConfirmModal {...defaultProps({ onConfirm, onCancel })} />);
    await user.click(screen.getByTestId('dataset-retire-confirm-cancel'));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('Esc key triggers onCancel', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(<DatasetRetireConfirmModal {...defaultProps({ onCancel })} />);
    await user.keyboard('{Escape}');
    expect(onCancel).toHaveBeenCalled();
  });

  it('disables both Cancel and Retire while isPending=true (in-flight mutation)', () => {
    render(
      <DatasetRetireConfirmModal
        {...defaultProps({ isPending: true })}
      />
    );
    expect(screen.getByTestId('dataset-retire-confirm-cancel')).toBeDisabled();
    // Even if the user has acknowledged, isPending shadows the enable.
    expect(screen.getByTestId('dataset-retire-confirm-cta')).toBeDisabled();
  });
});
