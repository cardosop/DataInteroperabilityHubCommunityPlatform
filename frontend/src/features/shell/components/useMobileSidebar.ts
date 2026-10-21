/**
 * Mobile sidebar hook — Phase 224.5.
 *
 * Split from ``MobileSidebarContext.tsx`` so that file can export *only*
 * components (satisfies the react-refresh lint rule: fast refresh needs a
 * module to export either all components or all non-components).
 */
import { useContext } from 'react';
import {
  MobileSidebarContext,
  FALLBACK_MOBILE_SIDEBAR,
} from './MobileSidebarContext';
import type { MobileSidebarContextValue } from './MobileSidebarContext';

export function useMobileSidebar(): MobileSidebarContextValue {
  const ctx = useContext(MobileSidebarContext);
  return ctx ?? FALLBACK_MOBILE_SIDEBAR;
}
