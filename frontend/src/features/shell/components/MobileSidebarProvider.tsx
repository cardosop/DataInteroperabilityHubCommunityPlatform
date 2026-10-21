/**
 * MobileSidebarProvider — Phase 224.5.
 * Owns the open/close state for the mobile sidebar overlay.
 */
import { useCallback, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  MobileSidebarContext,
  type MobileSidebarContextValue,
} from './MobileSidebarContext';

export function MobileSidebarProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((v) => !v), []);

  const value = useMemo<MobileSidebarContextValue>(
    () => ({ isOpen, open, close, toggle }),
    [isOpen, open, close, toggle],
  );

  return (
    <MobileSidebarContext.Provider value={value}>
      {children}
    </MobileSidebarContext.Provider>
  );
}
