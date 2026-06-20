/**
 * App Shell Component
 * Main layout wrapper with header and sidebar.
 *
 * Phase 224.5 — owns mobile-sidebar state via ``MobileSidebarProvider``.
 * The Header's hamburger toggles it, the Sidebar renders an overlay when
 * open, Escape / backdrop / link-click close it.
 */

import { useEffect, useMemo } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { CommandPalette } from '../../../shared/components/CommandPalette';
import type { PaletteItem } from '../../../shared/components/CommandPalette';
import { KeyboardShortcuts } from '../../../shared/components/KeyboardShortcuts';
import { FEATURE_SIDEBAR_ADVANCED } from '../../../shared/config/featureFlags';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import { SkipLink } from '../../../shared/components/SkipLink';
import { useAuthStore } from '../../auth/store/authStore';
import { isMvpModeEnabledFromEnv, isPathHiddenInMvpMode } from '../utils/mvpNav';
import { SIDEBAR_NAV_ITEMS } from '../utils/navItems';
import { filterVisibleNavItems } from '../utils/sidebarNavFilter';
import { flattenNavItemsForPalette } from '../utils/flattenNavItemsForPalette';
import './AppShell.css';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { MobileSidebarProvider } from './MobileSidebarProvider';
import { useMobileSidebar } from './useMobileSidebar';

/**
 * 223.5 — palette actions are verb-style shortcuts that don't appear in
 * the sidebar but are common enough to deserve a ⌘K entry. Track A PR 3:
 * filtered through isPathHiddenInMvpMode in MVP mode so /search doesn't
 * leak into the palette while the route is gated.
 */
const RAW_PALETTE_ACTIONS: PaletteItem[] = [
  { id: 'create-asset', label: 'Create Asset', path: '/assets/create' },
  { id: 'create-contract', label: 'Create Contract', path: '/contracts/create' },
  { id: 'search', label: 'Search', path: '/search' },
];

function ShellBody() {
  const { isOpen, close } = useMobileSidebar();
  const location = useLocation();

  // Track A PR 3: build palette pages by reusing the sidebar's
  // filterVisibleNavItems pipeline. Without this, the CommandPalette ⌘K
  // surface lists every nav item including /mesh, /baas, /search etc.
  // even when the sidebar correctly hides them under MVP mode.
  //
  // Memoise so the fuzzy-search index inside CommandPalette doesn't
  // rebuild on every ShellBody render — the deps array busts only when
  // auth/role/capability/MVP-flag actually change.
  const { user } = useAuthStore();
  const { isCapabilityAvailable } = useCapabilities();
  const mvpModeEnabled = isMvpModeEnabledFromEnv();

  const palettePages: PaletteItem[] = useMemo(() => {
    const hasRole = (requiredRoles?: string[]): boolean => {
      if (!requiredRoles || requiredRoles.length === 0) return true;
      if (!user) return false;
      return requiredRoles.some((role) => user.roles.includes(role));
    };
    const filtered = filterVisibleNavItems(SIDEBAR_NAV_ITEMS, {
      mvpModeEnabled,
      hasRole,
      isCapabilityAvailable,
      sidebarAdvancedEnabled: FEATURE_SIDEBAR_ADVANCED,
    });
    // Phase 240.4.A audit-fix Gap 1 — flatten sub-menu children into
    // the palette so ⌘K surfaces the new DQ sub-items (Anomalies /
    // Trends / Scorecards / Alerting Rules / Root Cause).  Without
    // this, the palette only ever lists the parent /dq link even
    // though the navItems comment marks itself as "the single source
    // of truth for the Sidebar AND CommandPalette".  Logic extracted
    // to ``flattenNavItemsForPalette`` so it's unit-testable in
    // isolation (the AppShell render suite is JSDOM-bound and can't
    // be relied on in environments without ResizeObserver).
    return flattenNavItemsForPalette(filtered);
  }, [user, isCapabilityAvailable, mvpModeEnabled]);

  const paletteActions: PaletteItem[] = useMemo(
    () =>
      RAW_PALETTE_ACTIONS.filter(
        (a) => !isPathHiddenInMvpMode(a.path, mvpModeEnabled),
      ),
    [mvpModeEnabled],
  );

  // Close the overlay on Escape and on route change — matches common mobile
  // nav UX so the panel doesn't stick around after navigation.
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [isOpen, close]);

  useEffect(() => {
    if (isOpen) close();
    // Only react to path changes, not to close() identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  return (
    <div
      className={`app-shell ${isOpen ? 'app-shell--sidebar-open' : ''}`}
      data-testid="app-shell"
      data-sidebar-open={isOpen ? 'true' : 'false'}
    >
      <SkipLink />
      <Header />
      {/* Phase 226.F1.b — testid for stable e2e selector. */}
      <div className="app-body" data-testid="app-body">
        <Sidebar />
        <main
          className="app-main"
          role="main"
          id="main-content"
          tabIndex={-1}
          data-testid="app-main"
        >
          <Outlet />
        </main>
      </div>
      <CommandPalette pages={palettePages} actions={paletteActions} />
      <KeyboardShortcuts />
    </div>
  );
}

export function AppShell() {
  return (
    <MobileSidebarProvider>
      <ShellBody />
    </MobileSidebarProvider>
  );
}
