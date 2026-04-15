/**
 * Mobile sidebar context & types — Phase 224.5.
 *
 * Non-TSX so the context value lives alongside the Provider/hook without
 * tripping the react-refresh lint rule (which requires .tsx files to export
 * only components).
 */
import { createContext } from 'react';

export interface MobileSidebarContextValue {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
}

export const MobileSidebarContext =
  createContext<MobileSidebarContextValue | null>(null);

/** No-op fallback so standalone Header/Sidebar tests don't need the provider. */
export const FALLBACK_MOBILE_SIDEBAR: MobileSidebarContextValue = {
  isOpen: false,
  open: () => undefined,
  close: () => undefined,
  toggle: () => undefined,
};
