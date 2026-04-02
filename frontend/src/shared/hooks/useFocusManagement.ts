/**
 * Focus Management Hook
 * Manages focus for modals, dialogs, and keyboard navigation
 */

import { useEffect, useRef } from 'react';

/**
 * Hook to trap focus within a modal/dialog
 */
export function useFocusTrap(isOpen: boolean): React.RefObject<HTMLDivElement | null> {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen || !containerRef.current) {
      return;
    }

    // Store the previously focused element
    previousActiveElementRef.current = document.activeElement as HTMLElement;

    // Get all focusable elements within the container
    const focusableSelectors = [
      'a[href]',
      'button:not([disabled])',
      'textarea:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      '[tabindex]:not([tabindex="-1"])',
    ].join(', ');

    const focusableElements = Array.from(
      containerRef.current.querySelectorAll<HTMLElement>(focusableSelectors)
    );

    if (focusableElements.length === 0) {
      return;
    }

    // Focus the first element
    focusableElements[0]?.focus();

    // Handle Tab key to cycle through focusable elements
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') {
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey) {
        // Shift+Tab: move backwards
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement?.focus();
        }
      } else {
        // Tab: move forwards
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement?.focus();
        }
      }
    };

    const currentContainer = containerRef.current;
    currentContainer.addEventListener('keydown', handleKeyDown);

    return () => {
      currentContainer.removeEventListener('keydown', handleKeyDown);
      // Restore focus to previously focused element
      previousActiveElementRef.current?.focus();
    };
  }, [isOpen]);

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
