/**
 * W5.4 (R2-F5) — focus-trap pins.
 *
 * Pre-fix the trap snapshotted the focusable list ONCE at open: content
 * added while the dialog is open (DestructiveConfirmDialog's typed-name
 * input) never joined the Tab cycle. The pin drives the REAL hook
 * through a host component in jsdom — no fake focus machinery.
 */

import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { useFocusTrap } from './useFocusManagement';

function TrapHost({ initialOpen }: { initialOpen: boolean }) {
  const [open, setOpen] = useState(initialOpen);
  const [extra, setExtra] = useState(false);
  const ref = useFocusTrap(open);

  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>
        Open dialog
      </button>
      {open && (
        <div ref={ref} role="dialog" aria-modal="true">
          <button type="button">First</button>
          <button type="button">Last</button>
          {extra && <button type="button">Dynamic</button>}
          <button type="button" onClick={() => setExtra(true)}>
            Add dynamic
          </button>
          <button type="button" onClick={() => setOpen(false)}>
            Close
          </button>
        </div>
      )}
    </div>
  );
}

describe('useFocusTrap', () => {
  it('focuses the first focusable element on open', async () => {
    const user = userEvent.setup();
    render(<TrapHost initialOpen={false} />);

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));

    expect(screen.getByRole('button', { name: 'First' })).toHaveFocus();
  });

  it('restores focus to the trigger on close', async () => {
    const user = userEvent.setup();
    render(<TrapHost initialOpen={false} />);

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));
    await user.click(screen.getByRole('button', { name: 'Close' }));

    expect(screen.getByRole('button', { name: 'Open dialog' })).toHaveFocus();
  });

  it('keeps Tab cycling between first and last', async () => {
    render(<TrapHost initialOpen />);

    // Native Tab behavior cannot be simulated in jsdom (userEvent's
    // synthetic tab steers focus itself and bypasses the trap) — drive
    // the REAL keydown events the browser would deliver.
    fireEvent.keyDown(screen.getByRole('button', { name: 'First' }), { key: 'Tab' });
    expect(screen.getByRole('button', { name: 'Last' })).toHaveFocus();
    fireEvent.keyDown(screen.getByRole('button', { name: 'Last' }), { key: 'Tab' });
    expect(screen.getByRole('button', { name: 'Add dynamic' })).toHaveFocus();
    fireEvent.keyDown(screen.getByRole('button', { name: 'Add dynamic' }), { key: 'Tab' });
    expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus();
    // Wraps from the end back to the first element.
    fireEvent.keyDown(screen.getByRole('button', { name: 'Close' }), { key: 'Tab' });
    expect(screen.getByRole('button', { name: 'First' })).toHaveFocus();
    // Shift+Tab wraps from the first back to the last.
    fireEvent.keyDown(screen.getByRole('button', { name: 'First' }), {
      key: 'Tab',
      shiftKey: true,
    });
    expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus();
  });

  it('includes dynamically-added elements in the Tab cycle (no stale snapshot)', async () => {
    const user = userEvent.setup();
    render(<TrapHost initialOpen />);

    // Add a button AFTER the dialog opened — the trap must notice it.
    await user.click(screen.getByRole('button', { name: 'Add dynamic' }));
    // The click moved focus to "Add dynamic"; park focus back on First so
    // the cycle starts from a known element (the trap cycles from the
    // CURRENT focus, as the browser would).
    screen.getByRole('button', { name: 'First' }).focus();

    // Cycle forward from First through the whole list; the dynamic button
    // must receive focus (pre-fix the stale snapshot skipped it).
    fireEvent.keyDown(screen.getByRole('button', { name: 'First' }), { key: 'Tab' });
    expect(screen.getByRole('button', { name: 'Last' })).toHaveFocus();
    fireEvent.keyDown(screen.getByRole('button', { name: 'Last' }), { key: 'Tab' });
    expect(screen.getByRole('button', { name: 'Dynamic' })).toHaveFocus();
  });
});
