/**
 * Focus Management Hook
 * Manages focus for modals, dialogs, and keyboard navigation
 */

import { useEffect, useRef } from 'react';

const FOCUSABLE_SELECTORS = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

/**
 * Hook to trap focus within a modal/dialog.
 *
 * W5.4 (R2-F5): the pre-fix trap snapshotted the focusable list ONCE at
 * open, so dynamically-added content (DestructiveConfirmDialog's typed
 * input) never joined the Tab cycle. The trap now re-scans on EVERY Tab
 * press and always drives the cycle itself — no stale snapshot, interior
 * elements included, and the container becomes focusable when empty.
 */
export function useFocusTrap<T extends HTMLElement = HTMLDivElement>(
  isOpen: boolean,
): React.RefObject<T | null> {
  const containerRef = useRef<T | null>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen || !containerRef.current) {
      return;
    }

    const container = containerRef.current;

    // Store the previously focused element for restore on close.
    previousActiveElementRef.current = document.activeElement as HTMLElement;

    const getFocusable = () =>
      Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTORS));

    // Initial focus: first focusable, or the container itself (made
    // focusable) so the trap still holds when the dialog is empty.
    const focusable = getFocusable();
    if (focusable.length > 0) {
      focusable[0].focus();
    } else {
      container.tabIndex = -1;
      container.focus();
    }

    // Drive every Tab press through the LIVE list (re-scanned per press).
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') {
        return;
      }

      const current = getFocusable();
      if (current.length === 0) {
        e.preventDefault();
        container.tabIndex = -1;
        container.focus();
        return;
      }

      const currentIndex = current.indexOf(document.activeElement as HTMLElement);
      const nextIndex = e.shiftKey
        ? currentIndex <= 0
          ? current.length - 1
          : currentIndex - 1
        : currentIndex >= current.length - 1
          ? 0
          : currentIndex + 1;

      e.preventDefault();
      current[nextIndex].focus();
    };

    container.addEventListener('keydown', handleKeyDown);

    return () => {
      container.removeEventListener('keydown', handleKeyDown);
      if (container.tabIndex === -1) {
        container.removeAttribute('tabindex');
      }
      // Restore focus to previously focused element
      previousActiveElementRef.current?.focus();
    };
  }, [isOpen]);

  return containerRef;
}

/**
 * W5.4 (R2-F5) — one-stop dialog a11y: focus trap + initial focus +
 * focus restore + Escape-to-close. The shared Modal already provides
 * this; custom hand-rolled dialogs adopt this hook to close the
 * keyboard-access gap (Tab escapes, no initial focus, no restore).
 */
export function useDialogA11y<T extends HTMLElement = HTMLDivElement>(
  isOpen: boolean,
  onClose: () => void,
): React.RefObject<T | null> {
  const containerRef = useFocusTrap<T>(isOpen);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  return containerRef;
}

/**
 * Hook to restore focus when a component unmounts
 */
export function useRestoreFocus() {
  const previousActiveElementRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previousActiveElementRef.current = document.activeElement as HTMLElement;

    return () => {
      previousActiveElementRef.current?.focus();
    };
  }, []);
}
