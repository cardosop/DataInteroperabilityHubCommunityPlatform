/**
 * App Shell Component
 * Main layout wrapper with header and sidebar.
 *
 * Phase 224.5 — owns mobile-sidebar state via ``MobileSidebarProvider``.
 * The Header's hamburger toggles it, the Sidebar renders an overlay when
 * open, Escape / backdrop / link-click close it.
 */

import { useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { CommandPalette } from '../../../shared/components/CommandPalette';
import type { PaletteItem } from '../../../shared/components/CommandPalette';
import { SkipLink } from '../../../shared/components/SkipLink';
import { SIDEBAR_NAV_ITEMS } from '../utils/navItems';
import './AppShell.css';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { MobileSidebarProvider } from './MobileSidebarProvider';
import { useMobileSidebar } from './useMobileSidebar';

/**
 * 223.5 — palette-indexed pages reuse the sidebar's single source of
 * truth. Actions are verb-style shortcuts that don't appear in the
 * sidebar but are common enough to deserve a ⌘K entry.
 */
const PALETTE_PAGES: PaletteItem[] = SIDEBAR_NAV_ITEMS.map((item) => ({
  label: item.label,
  path: item.path,
}));

const PALETTE_ACTIONS: PaletteItem[] = [
  { id: 'create-asset', label: 'Create Asset', path: '/assets/create' },
  { id: 'create-contract', label: 'Create Contract', path: '/contracts/create' },
  { id: 'search', label: 'Search', path: '/search' },
];

function ShellBody() {
  const { isOpen, close } = useMobileSidebar();
  const location = useLocation();

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
      <div className="app-body">
        <Sidebar />
        <main className="app-main" role="main" id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
      <CommandPalette pages={PALETTE_PAGES} actions={PALETTE_ACTIONS} />
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
