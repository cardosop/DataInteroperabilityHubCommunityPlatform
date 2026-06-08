/**
 * Warehouse Sidebar Navigation Item — Phase 275.D
 * Gated behind ``warehouse_connectivity_enabled`` tenant flag.
 */
import React from 'react';

interface Props { enabled?: boolean }

export function WarehouseSidebarItem({ enabled }: Props): React.ReactElement | null {
  if (!enabled) return null;
  return (
    <li className="nav-item">
      <a href="/warehouses/connections" title="Warehouse Connections">🏗️ Warehouses</a>
    </li>
  );
}
