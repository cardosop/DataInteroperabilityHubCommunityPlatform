import type { NavItem } from '../components/Sidebar';
import { isPathHiddenInMvpMode } from './mvpNav';

export function filterVisibleNavItems(
  items: NavItem[],
  options: {
    mvpModeEnabled: boolean;
    hasRole: (requiredRoles?: string[]) => boolean;
    isCapabilityAvailable: (key: string) => boolean;
  },
): NavItem[] {
  const { mvpModeEnabled, hasRole, isCapabilityAvailable } = options;
  return items.filter((item) => {
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
