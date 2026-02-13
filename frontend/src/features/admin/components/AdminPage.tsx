/**
 * Admin Page
 * Real admin interface with tenant/user management (role-gated)
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useAuthStore } from '../../auth/store/authStore';
import { useTenants, useUsers } from '../hooks/useAdmin';
import './AdminPage.css';

type AdminTab = 'overview' | 'tenants' | 'users';

export function AdminPage() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState<AdminTab>('overview');

  const isPlatformAdmin = user?.roles?.includes('PLATFORM_ADMIN') ?? false;
  const isTenantAdmin = user?.roles?.includes('TENANT_ADMIN') ?? false;
  const hasAdminAccess = isPlatformAdmin || isTenantAdmin;

  // Only fetch tenants if platform admin
  const tenantsQuery = useTenants({ page_size: 20 }, { enabled: isPlatformAdmin });
  // Fetch users (tenant-scoped or all for platform admin)
  const usersQuery = useUsers({ page_size: 20 });

  if (!hasAdminAccess) {
    return (
      <div className="admin-page" data-testid="admin-page">
        <div className="admin-no-permission">
          <h1>Admin Access Required</h1>
          <p>You do not have permission to access the admin area.</p>
          <p>This page requires TENANT_ADMIN or PLATFORM_ADMIN role.</p>
        </div>
      </div>
    );
  }

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return dateString;
    }
  };

  return (
    <div className="admin-page" data-testid="admin-page">
      <div className="admin-header">
        <h1>Admin</h1>
        <p className="subtitle">Platform and tenant administration</p>
      </div>

      <div className="admin-tabs">
        <button
          type="button"
          className={`admin-tab ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        {isPlatformAdmin && (
          <button
            type="button"
            className={`admin-tab ${activeTab === 'tenants' ? 'active' : ''}`}
            onClick={() => setActiveTab('tenants')}
          >
            Tenants
          </button>
        )}
        <button
          type="button"
          className={`admin-tab ${activeTab === 'users' ? 'active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          Users
        </button>
      </div>

      <div className="admin-content">
        {activeTab === 'overview' && (
          <section className="admin-section" data-testid="admin-overview-section">
            <h2>Admin Overview</h2>
            <div className="admin-links-grid">
              <Link to="/governance" className="admin-link-card">
                <span className="admin-link-icon">📋</span>
                <span className="admin-link-label">Governance</span>
                <span className="admin-link-desc">Access requests and policies</span>
              </Link>
              <Link to="/audit" className="admin-link-card">
                <span className="admin-link-icon">🔍</span>
                <span className="admin-link-label">Audit</span>
                <span className="admin-link-desc">View audit logs</span>
              </Link>
              {isPlatformAdmin && (
                <>
                  <div className="admin-link-card" onClick={() => setActiveTab('tenants')}>
                    <span className="admin-link-icon">🏢</span>
                    <span className="admin-link-label">Tenants</span>
                    <span className="admin-link-desc">Manage tenants</span>
                  </div>
                </>
              )}
              <div className="admin-link-card" onClick={() => setActiveTab('users')}>
                <span className="admin-link-icon">👥</span>
                <span className="admin-link-label">Users</span>
                <span className="admin-link-desc">Manage users</span>
              </div>
            </div>

            {isPlatformAdmin && tenantsQuery.data && (
              <div className="admin-stats">
                <div className="stat-card">
                  <span className="stat-value">{tenantsQuery.data.count || 0}</span>
                  <span className="stat-label">Total Tenants</span>
                </div>
              </div>
            )}

            {usersQuery.data && (
              <div className="admin-stats">
                <div className="stat-card">
                  <span className="stat-value">{usersQuery.data.count || 0}</span>
                  <span className="stat-label">Total Users</span>
                </div>
              </div>
            )}
          </section>
        )}

        {activeTab === 'tenants' && isPlatformAdmin && (
          <section className="admin-section" data-testid="admin-tenants-section">
            <div className="section-header">
              <h2>Tenants</h2>
            </div>
            {tenantsQuery.isLoading && <LoadingSpinner message="Loading tenants..." />}
            {tenantsQuery.error && (
              <ErrorDisplay error={tenantsQuery.error} title="Failed to load tenants" />
            )}
            {tenantsQuery.data && (
              <>
                {tenantsQuery.data.results.length === 0 ? (
                  <EmptyState message="No tenants found." />
                ) : (
                  <div className="admin-table-container">
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Slug</th>
                          <th>Status</th>
                          <th>KYC Status</th>
                          <th>Region</th>
                          <th>Created</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tenantsQuery.data.results.map((tenant) => (
                          <tr key={tenant.id}>
                            <td className="table-cell-name">{tenant.name}</td>
                            <td className="table-cell-slug">{tenant.slug}</td>
                            <td>
                              <span
                                className={`status-badge status-${tenant.status.toLowerCase()}`}
                              >
                                {tenant.status}
                              </span>
                            </td>
                            <td>
                              <span
                                className={`status-badge status-${tenant.kyc_status.toLowerCase()}`}
                              >
                                {tenant.kyc_status}
                              </span>
                            </td>
                            <td>{tenant.region || '-'}</td>
                            <td>{formatDate(tenant.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </section>
        )}

        {activeTab === 'users' && (
          <section className="admin-section" data-testid="admin-users-section">
            <div className="section-header">
              <h2>Users</h2>
            </div>
            {usersQuery.isLoading && <LoadingSpinner message="Loading users..." />}
            {usersQuery.error && (
              <ErrorDisplay error={usersQuery.error} title="Failed to load users" />
            )}
            {usersQuery.data && (
              <>
                {usersQuery.data.results.length === 0 ? (
                  <EmptyState message="No users found." />
                ) : (
                  <div className="admin-table-container">
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>Email</th>
                          <th>Display Name</th>
                          <th>Status</th>
                          <th>Roles</th>
                          <th>Tenant</th>
                          <th>Created</th>
                        </tr>
                      </thead>
                      <tbody>
                        {usersQuery.data.results.map((user) => (
                          <tr key={user.id}>
                            <td className="table-cell-email">{user.email}</td>
                            <td>{user.display_name || '-'}</td>
                            <td>
                              <span className={`status-badge status-${user.status.toLowerCase()}`}>
                                {user.status}
                              </span>
                            </td>
                            <td>
                              {user.roles && user.roles.length > 0 ? (
                                <div className="roles-list">
                                  {user.roles.map((role) => (
                                    <span key={role} className="role-badge">
                                      {role}
                                    </span>
                                  ))}
                                </div>
                              ) : (
                                '-'
                              )}
                            </td>
                            <td>{user.tenant_name || user.tenant || '-'}</td>
                            <td>{formatDate(user.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
