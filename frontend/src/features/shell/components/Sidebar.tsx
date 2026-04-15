/**
 * Sidebar Navigation Component
 * Role-aware sidebar navigation based on user roles
 */

import { NavLink } from 'react-router-dom';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import { useUnreadBadgeCounts } from '../../../shared/hooks/useUnreadBadgeCounts';
import { useAuthStore } from '../../auth/store/authStore';
import { isMvpModeEnabledFromEnv } from '../utils/mvpNav';
// 223.5 — navItems extracted to utils/navItems.ts so CommandPalette can
// reuse the same source of truth.
import { SIDEBAR_NAV_ITEMS, type NavItem } from '../utils/navItems';
import { filterVisibleNavItems } from '../utils/sidebarNavFilter';
import { useMobileSidebar } from './useMobileSidebar';
import './Sidebar.css';

// Re-export NavItem for consumers that imported it from this file.
export type { NavItem };

const navItems: NavItem[] = SIDEBAR_NAV_ITEMS;

export function Sidebar() {
  const { user } = useAuthStore();
  const { isCapabilityAvailable } = useCapabilities();
  const { governancePending } = useUnreadBadgeCounts();
  const { isOpen, close } = useMobileSidebar();

  const hasRole = (requiredRoles?: string[]): boolean => {
    if (!requiredRoles || requiredRoles.length === 0) return true;
    if (!user) return false;
    return requiredRoles.some((role) => user.roles.includes(role));
  };

  const decoratedNavItems: NavItem[] = navItems.map((item) =>
    item.path === '/governance'
      ? { ...item, badge: governancePending }
      : item,
  );

  const filteredNavItems = filterVisibleNavItems(decoratedNavItems, {
    mvpModeEnabled: isMvpModeEnabledFromEnv(),
    hasRole,
    isCapabilityAvailable,
  });

  // Group nav items into sections
  const corePaths = new Set(['/', '/assets', '/datasets', '/contracts']);
  const qualityPaths = new Set(['/dq', '/compliance']);
  const discoverPaths = new Set(['/search', '/marketplace']);
  const adminPaths = new Set(['/jobs', '/webhooks', '/observability', '/governance', '/audit', '/admin', '/files', '/semantic', '/scheduled-ingestions']);

  const coreItems = filteredNavItems.filter((i) => corePaths.has(i.path));
  const qualityItems = filteredNavItems.filter((i) => qualityPaths.has(i.path));
  const discoverItems = filteredNavItems.filter((i) => discoverPaths.has(i.path));
  const adminItems = filteredNavItems.filter((i) => adminPaths.has(i.path));
  const otherItems = filteredNavItems.filter(
    (i) => !corePaths.has(i.path) && !qualityPaths.has(i.path) && !discoverPaths.has(i.path) && !adminPaths.has(i.path),
  );

  const renderItems = (items: NavItem[]) =>
    items.map((item) => (
      <li key={item.path}>
        <NavLink
          to={item.path}
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          end={item.path === '/'}
        >
          {item.icon && <span className="nav-icon">{item.icon}</span>}
          <span className="nav-label">{item.label}</span>
          {item.badge !== undefined && item.badge > 0 && (
            <span
              className="nav-badge"
              aria-label={`${item.badge} pending`}
              data-testid={`nav-badge-${item.path}`}
            >
              {item.badge > 99 ? '99+' : item.badge}
            </span>
          )}
        </NavLink>
      </li>
    ));

  return (
    <>
      {/* Phase 224.5 — backdrop is only rendered when the mobile overlay is
          open. CSS hides the parent class at ≥ tablet so this button never
          renders inline on desktop. */}
      {isOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Close navigation"
          onClick={close}
          data-testid="sidebar-backdrop"
        />
      )}
      <aside
        id="app-sidebar"
        className={`app-sidebar ${isOpen ? 'app-sidebar--open' : ''}`}
        role="navigation"
        aria-label="Main navigation"
        aria-hidden={false}
      >
      <nav className="sidebar-nav">
        {coreItems.length > 0 && (
          <ul className="nav-list">{renderItems(coreItems)}</ul>
        )}
        {qualityItems.length > 0 && (
          <details className="nav-group" open>
            <summary className="nav-group__label">Quality & Compliance</summary>
            <ul className="nav-list">{renderItems(qualityItems)}</ul>
          </details>
        )}
        {discoverItems.length > 0 && (
          <details className="nav-group" open>
            <summary className="nav-group__label">Discover</summary>
            <ul className="nav-list">{renderItems(discoverItems)}</ul>
          </details>
        )}
        {otherItems.length > 0 && (
          <details className="nav-group" open>
            <summary className="nav-group__label">More</summary>
            <ul className="nav-list">{renderItems(otherItems)}</ul>
          </details>
        )}
        {adminItems.length > 0 && (
          <details className="nav-group">
            <summary className="nav-group__label">Admin</summary>
            <ul className="nav-list">{renderItems(adminItems)}</ul>
          </details>
        )}
      </nav>
    </aside>
    </>
  );
}
