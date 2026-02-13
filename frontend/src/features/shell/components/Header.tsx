/**
 * App Header Component
 * Tenant-aware header with tenant switcher, global search, and notifications
 */

import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../../auth/store/authStore';
import './Header.css';

export function Header() {
  const { user, logout } = useAuthStore();
  const [showTenantSwitcher, setShowTenantSwitcher] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    setShowUserMenu(false);
    await logout();
  };

  return (
    <header className="app-header" role="banner">
      <div className="header-content">
        <div className="header-left">
          <h1 className="app-title">Data Interoperability Hub</h1>
        </div>

        <div className="header-center">
          <input
            type="search"
            placeholder="Search assets, contracts, datasets..."
            className="global-search"
            aria-label="Global search"
          />
        </div>

        <div className="header-right">
          {user && (
            <>
              {/* Tenant Switcher */}
              <div className="tenant-switcher">
                <button
                  className="tenant-button"
                  onClick={() => setShowTenantSwitcher(!showTenantSwitcher)}
                  aria-label="Switch tenant"
                  aria-expanded={showTenantSwitcher}
                >
                  <span>{user.tenant_name || user.tenant_id}</span>
                  <span className="dropdown-arrow">▼</span>
                </button>
                {showTenantSwitcher && (
                  <div className="tenant-dropdown" role="menu">
                    <div className="tenant-current">
                      <strong>Current: {user.tenant_name || user.tenant_id}</strong>
                    </div>
                    {/* TODO: Implement tenant switching when endpoint available */}
                    <div className="tenant-option disabled">Switch tenant (coming soon)</div>
                  </div>
                )}
              </div>

              {/* Notifications */}
              <button
                className="notifications-button"
                onClick={() => setShowNotifications(!showNotifications)}
                aria-label="Notifications"
                aria-expanded={showNotifications}
              >
                🔔
                <span className="notification-badge">0</span>
              </button>

              {/* User Menu */}
              <div className="user-menu" ref={userMenuRef}>
                <button
                  type="button"
                  className="user-menu-trigger"
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  aria-expanded={showUserMenu}
                  aria-haspopup="true"
                  aria-label="User menu"
                >
                  <span className="user-name">{user.name || user.email}</span>
                  <span className="dropdown-arrow">▼</span>
                </button>
                {showUserMenu && (
                  <div className="user-menu-dropdown" role="menu">
                    <Link
                      to="/settings/sessions"
                      className="user-menu-item"
                      onClick={() => setShowUserMenu(false)}
                      role="menuitem"
                    >
                      Active sessions
                    </Link>
                    <Link
                      to="/settings/api-keys"
                      className="user-menu-item"
                      onClick={() => setShowUserMenu(false)}
                      role="menuitem"
                    >
                      API keys
                    </Link>
                    <button
                      type="button"
                      className="user-menu-item user-menu-logout"
                      onClick={handleLogout}
                      role="menuitem"
                    >
                      Logout
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
