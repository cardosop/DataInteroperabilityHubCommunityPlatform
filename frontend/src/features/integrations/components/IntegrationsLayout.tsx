/**
 * Integrations Layout
 * Tabs for Connections, Sync Jobs, Mappings to enable client-side navigation.
 * Avoids full page reload when switching sections (fixes E2E auth race on page.goto).
 */

import { NavLink, Outlet } from 'react-router-dom';
import './IntegrationsLayout.css';

export function IntegrationsLayout() {
  return (
    <div className="integrations-layout">
      <nav className="integrations-tabs" role="tablist" aria-label="Integrations sections">
        <NavLink
          to="/integrations/connections"
          className={({ isActive }) => `integrations-tab ${isActive ? 'active' : ''}`}
          end={false}
        >
          Connections
        </NavLink>
        <NavLink
          to="/integrations/sync-jobs"
          className={({ isActive }) => `integrations-tab ${isActive ? 'active' : ''}`}
          end={false}
        >
          Sync Jobs
        </NavLink>
        <NavLink
          to="/integrations/mappings"
          className={({ isActive }) => `integrations-tab ${isActive ? 'active' : ''}`}
          end={false}
        >
          Mappings
        </NavLink>
      </nav>
      <div className="integrations-content">
        <Outlet />
      </div>
    </div>
  );
}
