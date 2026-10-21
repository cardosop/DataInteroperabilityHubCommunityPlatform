/**
 * W5.4 (R2-F5) — keyboard-shortcuts cheatsheet focus pins.
 *
 * The E2E spec asserts the close button receives focus on open — the
 * pre-fix component never did it (no trap, no initial focus, no
 * aria-modal). Pins: open via `?` → close button focused; Escape
 * closes and restores focus to the trigger.
 */

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { KeyboardShortcuts } from './KeyboardShortcuts';

function openCheatsheet() {
  fireEvent.keyDown(window, { key: '?' });
}

describe('KeyboardShortcuts', () => {
  it('declares the dialog modal and focuses the close button on open', () => {
    render(<KeyboardShortcuts />);

    openCheatsheet();

    const dialog = screen.getByTestId('keyboard-shortcuts');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByRole('button', { name: /close shortcuts/i })).toHaveFocus();
  });

  it('closes on Escape', () => {
    render(<KeyboardShortcuts />);

    openCheatsheet();
    expect(screen.getByTestId('keyboard-shortcuts')).toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByTestId('keyboard-shortcuts')).not.toBeInTheDocument();
  });

  it('keeps Tab inside the dialog', () => {
    render(<KeyboardShortcuts />);

    openCheatsheet();
    // The only focusable element is the close button — Tab must wrap to it.
    fireEvent.keyDown(screen.getByRole('button', { name: /close shortcuts/i }), {
      key: 'Tab',
    });
    expect(screen.getByRole('button', { name: /close shortcuts/i })).toHaveFocus();
  });
});
