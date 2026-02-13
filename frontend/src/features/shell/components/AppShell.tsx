/**
 * App Shell Component
 * Main layout wrapper with header and sidebar
 */

import { Outlet } from 'react-router-dom';
import { SkipLink } from '../../../shared/components/SkipLink';
import './AppShell.css';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

export function AppShell() {
  return (
    <div className="app-shell">
      <SkipLink />
      <Header />
      <div className="app-body">
        <Sidebar />
        <main className="app-main" role="main" id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
