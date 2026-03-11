/**
 * App Header Component
 * Tenant-aware header with tenant switcher, global search, and notifications
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../../auth/store/authStore';
import { getMyTenants, switchTenant } from '../../auth/services/tenantSwitchService';
import type { TenantSummary } from '../../auth/types/tenantSwitch';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { APP_NAME } from '../../../shared/constants/brand';
import './Header.css';

function getErrorMessage(err: unknown, fallback: string): string {
  return normalizeError(err).error.message || fallback;
}

export function Header() {
  const { user, active_tenant_id, setActiveTenant, refreshUser, logout } = useAuthStore();
  const [showTenantSwitcher, setShowTenantSwitcher] = useState(false);
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [tenantLoading, setTenantLoading] = useState(false);
  const [tenantSwitching, setTenantSwitching] = useState(false);
  const [tenantError, setTenantError] = useState<string | null>(null);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const tenantSwitcherRef = useRef<HTMLDivElement>(null);
  const notificationsRef = useRef<HTMLDivElement>(null);

  const effectiveTenantId = active_tenant_id || user?.tenant_id;
  const currentTenant = tenants.find((t) => t.id === effectiveTenantId);
  const displayName = currentTenant?.name || user?.tenant_name || effectiveTenantId || 'Tenant';

  const loadTenants = useCallback(async () => {
    setTenantLoading(true);
    setTenantError(null);
    try {
      const list = await getMyTenants();
      setTenants(list);
    } catch (err) {
      setTenantError(getErrorMessage(err, 'Failed to load tenants'));
      setTenants([]);
    } finally {
      setTenantLoading(false);
    }
  }, []);

  useEffect(() => {
    if (showTenantSwitcher && user) {
      loadTenants();
    }
  }, [showTenantSwitcher, user, loadTenants]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
      if (tenantSwitcherRef.current && !tenantSwitcherRef.current.contains(e.target as Node)) {
        setShowTenantSwitcher(false);
      }
      if (notificationsRef.current && !notificationsRef.current.contains(e.target as Node)) {
        setShowNotifications(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setShowNotifications(false);
        setShowUserMenu(false);
        setShowTenantSwitcher(false);
      }
    };
    document.addEventListener('click', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('click', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const handleSwitchTenant = async (tenantId: string) => {
    if (tenantId === effectiveTenantId) {
      setShowTenantSwitcher(false);
      return;
    }
    setTenantError(null);
    setTenantSwitching(true);
    try {
      const updatedUser = await switchTenant(tenantId);
      setActiveTenant(tenantId);
      await refreshUser(updatedUser);
      setShowTenantSwitcher(false);
    } catch (err) {
      setTenantError(getErrorMessage(err, 'Failed to switch tenant'));
    } finally {
      setTenantSwitching(false);
    }
  };

  const handleLogout = async () => {
    setShowUserMenu(false);
    await logout();
  };

  return (
    <header className="app-header" role="banner">
      <div className="header-content">
        <div className="header-left">
          <Link to="/" className="app-title-link" aria-label={`${APP_NAME} — go to home`}>
            <h1 className="app-title">{APP_NAME}</h1>
          </Link>
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
              {/* Tenant Switcher — only when feature enabled (default true); else static tenant name */}
              {user.feature_tenant_switch_enabled !== false ? (
              <div className="tenant-switcher" ref={tenantSwitcherRef}>
                <button
                  className="tenant-button"
                  onClick={() => setShowTenantSwitcher(!showTenantSwitcher)}
                  aria-label="Switch tenant"
                  aria-expanded={showTenantSwitcher}
                  aria-haspopup="true"
                >
                  <span>{displayName}</span>
                  <span className="dropdown-arrow">▼</span>
                </button>
                {showTenantSwitcher && (
                  <div className="tenant-dropdown" role="menu">
                    <div className="tenant-current">
                      <strong>Current: {displayName}</strong>
                    </div>
                    {tenantError && (
                      <div className="tenant-error" role="alert">
                        {tenantError}
                      </div>
                    )}
                    {tenantLoading ? (
                      <div className="tenant-option disabled">Loading tenants...</div>
                    ) : tenantSwitching ? (
                      <div className="tenant-option disabled">Switching...</div>
                    ) : tenants.length === 0 ? (
                      <div className="tenant-option disabled">No tenants</div>
                    ) : (
                      tenants.map((t) => (
                        <button
                          key={t.id}
                          type="button"
                          className={`tenant-option ${t.id === effectiveTenantId ? 'active' : ''}`}
                          onClick={() => handleSwitchTenant(t.id)}
                          disabled={tenantSwitching}
                          role="menuitem"
                        >
                          {t.name}
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>
              ) : (
              <span className="tenant-static" title={displayName}>{displayName}</span>
              )}

              {/* Notifications — minimal placeholder until backend support */}
              <div className="notifications-wrapper" ref={notificationsRef}>
                <button
                  type="button"
                  className="notifications-button"
                  onClick={() => setShowNotifications(!showNotifications)}
                  aria-label="Notifications"
                  aria-expanded={showNotifications}
                  aria-haspopup="true"
                >
                  🔔
                  <span className="notification-badge" aria-hidden="true">0</span>
                </button>
                {showNotifications && (
                  <div
                    className="notifications-dropdown"
                    role="region"
                    aria-label="Notifications"
                    data-testid="notifications-dropdown"
                  >
                    <div className="notifications-empty">
                      <p className="notifications-empty-title">No notifications yet</p>
                      <p className="notifications-empty-message">
                        Notifications will appear here when you have updates (e.g. access requests, DQ results).
                      </p>
                    </div>
                  </div>
                )}
              </div>

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
                      to="/settings/profile"
                      className="user-menu-item"
                      onClick={() => setShowUserMenu(false)}
                      role="menuitem"
                    >
                      Profile
                    </Link>
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
                    <Link
                      to="/settings/privacy"
                      className="user-menu-item"
                      onClick={() => setShowUserMenu(false)}
                      role="menuitem"
                    >
                      Privacy & data
                    </Link>
                    {(user.roles?.includes('TENANT_ADMIN') || user.roles?.includes('PLATFORM_ADMIN')) && (
                      <>
                        <Link
                          to="/settings/tenant"
                          className="user-menu-item"
                          onClick={() => setShowUserMenu(false)}
                          role="menuitem"
                        >
                          Tenant settings
                        </Link>
                        <Link
                          to="/settings/subscription"
                          className="user-menu-item"
                          onClick={() => setShowUserMenu(false)}
                          role="menuitem"
                        >
                          Subscription
                        </Link>
                        <Link
                          to="/settings/cost"
                          className="user-menu-item"
                          onClick={() => setShowUserMenu(false)}
                          role="menuitem"
                        >
                          Cost tracking
                        </Link>
                      </>
                    )}
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
