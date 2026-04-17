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
  return items.filter((item) => {
    // Feature flag: hide advanced items when sidebar advanced flag is disabled
    if (item.advanced && !sidebarAdvancedEnabled) {
      return false;
    }
    if (isPathHiddenInMvpMode(item.path, mvpModeEnabled)) {
      return false;
    }
    if (!hasRole(item.requiredRole)) {
      return false;
    }
    if (item.requiredCapability) {
      return isCapabilityAvailable(item.requiredCapability);
    }
    return true;
  });
}
