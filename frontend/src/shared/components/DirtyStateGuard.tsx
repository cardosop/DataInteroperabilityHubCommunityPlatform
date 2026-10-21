/**
 * DirtyStateGuard — W5.4 (R2-F5)
 *
 * Shared unsaved-changes guard adopted by wizard and create flows.
 * When ``dirty`` is true it:
 *
 *   - blocks in-app navigation (react-router ``useBlocker`` — links,
 *     programmatic ``navigate()``, and browser back/forward) and shows a
 *     ConfirmDialog offering Discard / Keep editing;
 *   - registers a ``beforeunload`` listener so a tab close or reload also
 *     prompts the browser's native confirmation.
 *
 * Renders nothing while clean. Requires the data router
 * (``createBrowserRouter``/``createMemoryRouter``) — the app uses one at
 * the root, so any page inside the route tree can adopt it.
 */

import { useCallback, useEffect, useRef } from 'react';
import { useBlocker } from 'react-router-dom';
import { ConfirmDialog } from './ConfirmDialog';

export interface DirtyStateGuardProps {
  /** True while the page holds unsaved changes. */
  dirty: boolean;
  /** Optional custom confirmation copy. */
  message?: string;
}

const DEFAULT_MESSAGE =
  'You have unsaved changes. Leaving this page will discard them.';

export function DirtyStateGuard({ dirty, message }: DirtyStateGuardProps) {
  // The blocker must see the LATEST dirty value, not the render-closure
  // one: flows that persist-then-navigate in the same tick (wizard submit
  // clears dirty and redirects synchronously) would otherwise block their
  // own post-save navigation.
  const dirtyRef = useRef(dirty);
  useEffect(() => {
    dirtyRef.current = dirty;
  }, [dirty]);

  const blocker = useBlocker(
    useCallback(
      ({
        currentLocation,
        nextLocation,
      }: {
        currentLocation: { pathname: string };
        nextLocation: { pathname: string };
      }) =>
        dirtyRef.current && currentLocation.pathname !== nextLocation.pathname,
      [],
    ),
  );

  // Browser tab close / reload guard — only while dirty.
  useEffect(() => {
    if (!dirty) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      // Required for Chrome to show the native confirmation dialog.
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [dirty]);

  if (blocker.state !== 'blocked') return null;

  return (
    <ConfirmDialog
      isOpen
      onClose={() => blocker.reset?.()}
      onConfirm={() => blocker.proceed?.()}
      title="Discard unsaved changes?"
      message={message ?? DEFAULT_MESSAGE}
      confirmLabel="Discard changes"
      cancelLabel="Keep editing"
      variant="warning"
    />
  );
}
