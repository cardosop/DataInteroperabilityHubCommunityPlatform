import type { NavItem } from '../components/Sidebar';
import { isPathHiddenInMvpMode } from './mvpNav';

export function filterVisibleNavItems(
  items: NavItem[],
  options: {
    mvpModeEnabled: boolean;
    hasRole: (requiredRoles?: string[]) => boolean;
    isCapabilityAvailable: (key: string) => boolean;
    /** When false, items with `advanced: true` are hidden from the sidebar.
     *  Controlled by VITE_FEATURE_SIDEBAR_ADVANCED env var. Default: true. */
    sidebarAdvancedEnabled?: boolean;
  },
): NavItem[] {
  const { mvpModeEnabled, hasRole, isCapabilityAvailable, sidebarAdvancedEnabled = true } = options;

  // Phase 240.4.A.9 — recursive filter that respects role / capability
  // gates on sub-items too.  When ALL children of a parent are hidden
  // (e.g. tenant doesn't have ``data_quality_advanced_enabled``), the
  // parent stays visible WITHOUT the sub-menu so basic DQ navigation
  // remains accessible.
  const filterOne = (item: NavItem): NavItem | null => {
    if (item.advanced && !sidebarAdvancedEnabled) return null;
    if (isPathHiddenInMvpMode(item.path, mvpModeEnabled)) return null;
    if (!hasRole(item.requiredRole)) return null;
    if (item.requiredCapability && !isCapabilityAvailable(item.requiredCapability)) {
      return null;
    }
    if (item.children && item.children.length > 0) {
      const visibleChildren = item.children
        .map(filterOne)
        .filter((c): c is NavItem => c !== null);
      if (visibleChildren.length === 0) {
        // Hide the children block (parent-only) when no child passed
        // its gates.  Falls back to the parent's own link.
        return { ...item, children: undefined };
      }
      return { ...item, children: visibleChildren };
    }
    return item;
  };

  return items.map(filterOne).filter((i): i is NavItem => i !== null);
}
