/**
 * useKeyboardShortcut — 223.5.2 tests.
 *
 * Verifies keyboard binding semantics with real `window` events:
 *   - plain key firing
 *   - modifier-gated firing (ctrl/meta/shift/alt)
 *   - `preventDefault` on match
 *   - non-match is a no-op
 *   - cross-platform `modOrCtrl` shorthand matches both `ctrlKey` and `metaKey`
 *   - cleanup removes the listener on unmount
 */
import { renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useKeyboardShortcut } from './useKeyboardShortcut';

/** Helper: dispatch a real KeyboardEvent against `window`. */
function fire(
  key: string,
  opts: {
    ctrlKey?: boolean;
    metaKey?: boolean;
    shiftKey?: boolean;
    altKey?: boolean;
    target?: EventTarget;
  } = {},
): KeyboardEvent {
  const event = new KeyboardEvent('keydown', {
    key,
    ctrlKey: opts.ctrlKey,
    metaKey: opts.metaKey,
    shiftKey: opts.shiftKey,
    altKey: opts.altKey,
    bubbles: true,
    cancelable: true,
  });
  (opts.target ?? window).dispatchEvent(event);
  return event;
}

describe('useKeyboardShortcut', () => {
  afterEach(() => vi.restoreAllMocks());

  it('fires the handler on a plain key match', () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut({ key: 'Escape' }, handler));
    fire('Escape');
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('does not fire when the key differs', () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut({ key: 'Escape' }, handler));
    fire('Enter');
    expect(handler).not.toHaveBeenCalled();
  });

  it('requires ctrl when ctrl is in the binding', () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut({ key: 'k', ctrl: true }, handler));
    fire('k'); // plain k — skip
    expect(handler).not.toHaveBeenCalled();
    fire('k', { ctrlKey: true });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('modOrCtrl matches both ctrl (Win/Linux) and meta (macOS)', () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut({ key: 'k', modOrCtrl: true }, handler));
    fire('k', { ctrlKey: true });
    fire('k', { metaKey: true });
    expect(handler).toHaveBeenCalledTimes(2);
  });

  it('calls preventDefault on a match by default', () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut({ key: 'k', modOrCtrl: true }, handler));
    const ev = fire('k', { ctrlKey: true });
    expect(ev.defaultPrevented).toBe(true);
  });

  it('key match is case-insensitive', () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut({ key: 'K', modOrCtrl: true }, handler));
    fire('k', { ctrlKey: true });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('skips the shortcut while focus is inside an editable element', () => {
    // Typing Ctrl+K in a search box must not hijack to open the palette.
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut({ key: 'k', modOrCtrl: true }, handler));
    const input = document.createElement('input');
    document.body.appendChild(input);
    input.focus();
    const ev = new KeyboardEvent('keydown', {
      key: 'k',
      ctrlKey: true,
      bubbles: true,
      cancelable: true,
    });
    input.dispatchEvent(ev);
    expect(handler).not.toHaveBeenCalled();
    document.body.removeChild(input);
  });

  it('cleans up the listener on unmount', () => {
    const handler = vi.fn();
    const { unmount } = renderHook(() =>
      useKeyboardShortcut({ key: 'Escape' }, handler),
    );
    unmount();
    fire('Escape');
    expect(handler).not.toHaveBeenCalled();
  });
});
