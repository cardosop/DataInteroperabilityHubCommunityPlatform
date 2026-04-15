/**
 * Admin Page
 * Real admin interface with tenant/user management (role-gated)
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useAuthStore } from '../../auth/store/authStore';
import {
  useCreateTenant,
  usePlatformTenantUsage,
  useResumeTenant,
  useSuspendTenant,
  useTenants,
  useUsers,
} from '../hooks/useAdmin';
import './AdminPage.css';

type AdminTab = 'overview' | 'tenants' | 'usage' | 'users';

export function AdminPage() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState<AdminTab>('overview');

  const isPlatformAdmin = user?.roles?.includes('PLATFORM_ADMIN') ?? false;
  const isTenantAdmin = user?.roles?.includes('TENANT_ADMIN') ?? false;
  const hasAdminAccess = isPlatformAdmin || isTenantAdmin;

  // Create organization form state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newOrgName, setNewOrgName] = useState('');
  const [newOrgSlug, setNewOrgSlug] = useState('');
  const [newOrgRegion, setNewOrgRegion] = useState('');

  // Only fetch tenants if platform admin
  const tenantsQuery = useTenants({ page_size: 20 }, { enabled: isPlatformAdmin });
  const usageQuery = usePlatformTenantUsage({ enabled: isPlatformAdmin });
  const createTenantMutation = useCreateTenant();
  const suspendTenantMutation = useSuspendTenant();
  const resumeTenantMutation = useResumeTenant();
  // Fetch users (tenant-scoped or all for platform admin)
  const usersQuery = useUsers({ page_size: 20 });

  if (!hasAdminAccess) {
    return (
      <div className="admin-page" data-testid="admin-page">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Admin' },
          ]}
        />
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
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Admin' },
        ]}
      />
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
        {isPlatformAdmin && (
          <button
            type="button"
            className={`admin-tab ${activeTab === 'usage' ? 'active' : ''}`}
            onClick={() => setActiveTab('usage')}
          >
            Usage
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
                  <div className="admin-link-card" onClick={() => setActiveTab('usage')}>
                    <span className="admin-link-icon">📊</span>
                    <span className="admin-link-label">Usage</span>
                    <span className="admin-link-desc">Usage across tenants</span>
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
              <button
                type="button"
                className="admin-action-btn"
                data-testid="create-tenant-btn"
                onClick={() => setShowCreateForm(!showCreateForm)}
              >
                {showCreateForm ? 'Cancel' : '+ Create Organization'}
              </button>
            </div>
            {showCreateForm && (
              <form
                className="admin-create-form"
                data-testid="create-tenant-form"
                onSubmit={async (e) => {
                  e.preventDefault();
                  await createTenantMutation.mutateAsync({
                    name: newOrgName.trim(),
                    slug: newOrgSlug.trim() || newOrgName.trim().toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, ''),
                    region: newOrgRegion.trim() || undefined,
                  });
                  setNewOrgName('');
                  setNewOrgSlug('');
                  setNewOrgRegion('');
                  setShowCreateForm(false);
                }}
              >
                <div className="form-group">
                  <label htmlFor="org-name">Organization Name *</label>
                  <input
                    id="org-name"
                    type="text"
                    value={newOrgName}
                    onChange={(e) => {
                      setNewOrgName(e.target.value);
                      if (!newOrgSlug) {
                        setNewOrgSlug(e.target.value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, ''));
                      }
                    }}
                    required
                    placeholder="Acme Corp"
                    data-testid="create-tenant-name"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="org-slug">Slug *</label>
                  <input
                    id="org-slug"
                    type="text"
                    value={newOrgSlug}
                    onChange={(e) => setNewOrgSlug(e.target.value)}
                    required
                    placeholder="acme-corp"
                    pattern="^[a-zA-Z0-9_\-]+$"
                    data-testid="create-tenant-slug"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="org-region">Region</label>
                  <input
                    id="org-region"
                    type="text"
                    value={newOrgRegion}
                    onChange={(e) => setNewOrgRegion(e.target.value)}
                    placeholder="us-east-1"
                    data-testid="create-tenant-region"
                  />
                </div>
                {createTenantMutation.error != null ? (
                  <ErrorDisplay error={createTenantMutation.error} title="Failed to create organization" />
                ) : null}
                <button
                  type="submit"
                  className="admin-action-btn"
                  disabled={createTenantMutation.isPending || !newOrgName.trim()}
                  data-testid="create-tenant-submit"
                >
                  {createTenantMutation.isPending ? 'Creating...' : 'Create Organization'}
                </button>
              </form>
            )}
            {tenantsQuery.isLoading && <LoadingSpinner message="Loading tenants..." />}
            {tenantsQuery.error && (
              <ErrorDisplay error={tenantsQuery.error} title="Failed to load tenants" />
            )}
            {!!(suspendTenantMutation.error || resumeTenantMutation.error) && (
              <ErrorDisplay
                error={suspendTenantMutation.error ?? resumeTenantMutation.error}
                title="Tenant action failed"
                onRetry={() => {
                  suspendTenantMutation.reset();
                  resumeTenantMutation.reset();
                }}
              />
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
                          <th>Actions</th>
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
                            <td>
                              {tenant.status === 'ACTIVE' && (
                                <button
                                  type="button"
                                  className="admin-action-btn admin-action-suspend"
                                  onClick={() =>
                                    suspendTenantMutation.mutate({ id: tenant.id })
                                  }
                                  disabled={suspendTenantMutation.isPending}
                                  data-testid={`suspend-tenant-${tenant.id}`}
                                >
                                  Suspend
                                </button>
                              )}
                              {tenant.status === 'SUSPENDED' && (
                                <button
                                  type="button"
                                  className="admin-action-btn admin-action-resume"
                                  onClick={() =>
                                    resumeTenantMutation.mutate({ id: tenant.id })
                                  }
                                  disabled={resumeTenantMutation.isPending}
                                  data-testid={`resume-tenant-${tenant.id}`}
                                >
                                  Resume
                                </button>
                              )}
                              {tenant.status === 'DELETED' && (
                                <span className="admin-action-disabled">—</span>
                              )}
                            </td>
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

        {activeTab === 'usage' && isPlatformAdmin && (
          <section className="admin-section" data-testid="admin-usage-section">
            <div className="section-header">
              <h2>Tenant Usage</h2>
              {usageQuery.data && (
                <span className="usage-period">
                  {new Date(usageQuery.data.period_start).toLocaleDateString('en-US', {
                    month: 'short',
                    year: 'numeric',
                  })}
                </span>
              )}
            </div>
            {usageQuery.isLoading && <LoadingSpinner message="Loading usage..." />}
            {usageQuery.error && (
              <ErrorDisplay error={usageQuery.error} title="Failed to load usage" />
            )}
            {usageQuery.data && (
              <>
                {usageQuery.data.results.length === 0 ? (
                  <EmptyState message="No tenant usage data." />
                ) : (
                  <div className="admin-table-container">
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>Tenant</th>
                          <th>Plan</th>
                          <th>Assets</th>
                          <th>Datasets</th>
                          <th>API Calls</th>
                          <th>Storage (GB)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {usageQuery.data.results.map((row) => (
                          <tr key={row.tenant_id}>
                            <td>
                              <span className="table-cell-name">{row.tenant_name}</span>
                              <span className="table-cell-slug-muted">{row.tenant_slug}</span>
                            </td>
                            <td>{row.plan_slug ?? row.plan_tier ?? '-'}</td>
                            <td>{row.usage.asset_count}</td>
                            <td>{row.usage.dataset_count}</td>
                            <td>{row.usage.api_calls_count}</td>
                            <td>{(row.usage.storage_gb ?? 0).toFixed(2)}</td>
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
                          <th>Actions</th>
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
                                  {user.roles.map((role, idx) => {
                                    const roleName =
                                      typeof role === 'object' && role !== null && 'name' in role
                                        ? (role as { name: string }).name
                                        : String(role);
                                    const roleKey =
                                      typeof role === 'object' && role !== null && 'id' in role
                                        ? (role as { id: string }).id
                                        : `${roleName}-${idx}`;
                                    return (
                                      <span key={roleKey} className="role-badge">
                                        {roleName}
                                      </span>
                                    );
                                  })}
                                </div>
                              ) : (
                                '-'
                              )}
                            </td>
                            <td>
                              {user.tenant_name ??
                                (typeof user.tenant === 'object' && user.tenant !== null && 'name' in user.tenant
                                  ? (user.tenant as { name: string }).name
                                  : typeof user.tenant === 'string'
                                    ? user.tenant
                                    : '-')}
                            </td>
                            <td>{formatDate(user.created_at)}</td>
                            <td>
                              <Link
                                to={`/admin/users/${user.id}/edit`}
                                className="admin-user-edit-link"
                              >
                                Edit
                              </Link>
                            </td>
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
