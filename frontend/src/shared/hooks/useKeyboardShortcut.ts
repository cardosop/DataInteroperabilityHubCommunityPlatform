/**
 * useKeyboardShortcut — 223.5.2.
 *
 * Global keyboard listener with declarative binding. Handles:
 *   - cross-platform modifiers (`modOrCtrl` = ctrl on Win/Linux, ⌘ on macOS)
 *   - case-insensitive key match
 *   - opt-out `preventDefault` (defaults to preventing — palette shortcuts
 *     should never also insert a character into whatever input was focused)
 *   - "don't hijack the user's text input": when focus is inside an
 *     `<input>`, `<textarea>`, `<select>`, or `contenteditable`, the
 *     shortcut is ignored so users can still type Ctrl-K to delete-to-eol
 *     inside Slack, for example. The one exception is `Escape`, which
 *     pages rely on for dismissal semantics.
 *   - clean listener teardown on unmount.
 */

import { useEffect } from 'react';

export interface KeyboardBinding {
  /** Key name (`event.key`). Case-insensitive; e.g. `'k'` matches `'K'`. */
  key: string;
  /** Require `event.ctrlKey`. */
  ctrl?: boolean;
  /** Require `event.metaKey`. */
  meta?: boolean;
  /** Either ctrl OR meta — pick the right one for the platform. */
  modOrCtrl?: boolean;
  /** Require `event.shiftKey`. */
  shift?: boolean;
  /** Require `event.altKey`. */
  alt?: boolean;
  /** Disable `preventDefault()` when the binding fires. Default `false`. */
  allowDefault?: boolean;
  /**
   * Fire the shortcut even when focus is inside an editable element.
   * Default `false` for all keys *except* Escape, where dismissal is
   * typically the desired behaviour inside fields too.
   */
  allowInEditable?: boolean;
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (target.isContentEditable) return true;
  return false;
}

export function useKeyboardShortcut(
  binding: KeyboardBinding,
  handler: (event: KeyboardEvent) => void,
): void {
  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== binding.key.toLowerCase()) return;

      if (binding.modOrCtrl) {
        if (!event.ctrlKey && !event.metaKey) return;
      } else {
        if (!!binding.ctrl !== event.ctrlKey) return;
        if (!!binding.meta !== event.metaKey) return;
      }
      if (binding.shift !== undefined && !!binding.shift !== event.shiftKey) return;
      if (binding.alt !== undefined && !!binding.alt !== event.altKey) return;

      const allowEditable = binding.allowInEditable ?? binding.key === 'Escape';
      if (!allowEditable && isEditableTarget(event.target)) return;

      if (!binding.allowDefault) {
        event.preventDefault();
      }
      handler(event);
    };

    window.addEventListener('keydown', listener);
    return () => window.removeEventListener('keydown', listener);
  }, [
    binding.key,
    binding.ctrl,
    binding.meta,
    binding.modOrCtrl,
    binding.shift,
    binding.alt,
    binding.allowDefault,
    binding.allowInEditable,
    handler,
  ]);
}
