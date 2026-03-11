/**
 * User Edit Page
 * Edit user roles and status. Requires TENANT_ADMIN or PLATFORM_ADMIN.
 * Route: /admin/users/:id/edit
 */

import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useRoles, useUpdateUser, useUser } from '../hooks/useAdmin';
import './UserEditPage.css';

const USER_STATUSES = [
  { value: 'ACTIVE', label: 'Active' },
  { value: 'INVITED', label: 'Invited' },
  { value: 'DISABLED', label: 'Disabled' },
  { value: 'SUSPENDED', label: 'Suspended' },
] as const;

function getRoleName(role: string | { id?: string; name?: string }): string {
  return typeof role === 'string' ? role : role?.name ?? '';
}

export function UserEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState('');
  const [status, setStatus] = useState<string>('ACTIVE');
  const [selectedRoleIds, setSelectedRoleIds] = useState<Set<string>>(new Set());

  const { data: user, isLoading: userLoading, error: userError } = useUser(id ?? null);
  const { data: roles, isLoading: rolesLoading } = useRoles();
  const updateMutation = useUpdateUser();

  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name ?? '');
      setStatus(user.status ?? 'ACTIVE');
    }
  }, [user]);

  useEffect(() => {
    if (user?.roles && roles && roles.length > 0) {
      const ids = new Set<string>();
      for (const roleName of user.roles.map(getRoleName)) {
        const r = roles.find((ro) => ro.name === roleName);
        if (r) ids.add(r.id);
      }
      setSelectedRoleIds(ids);
    }
  }, [user?.roles, roles]);

  const handleRoleToggle = (roleId: string) => {
    setSelectedRoleIds((prev) => {
      const next = new Set(prev);
      if (next.has(roleId)) next.delete(roleId);
      else next.add(roleId);
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    try {
      await updateMutation.mutateAsync({
        id,
        data: {
          display_name: displayName.trim() || undefined,
          status,
          role_ids: Array.from(selectedRoleIds),
        },
      });
      navigate('/admin');
    } catch {
      // Error shown via mutation
    }
  };

  if (userLoading && !user) {
    return <LoadingSpinner message="Loading user..." />;
  }

  if (userError) {
    return (
      <ErrorDisplay
        error={userError as Error}
        title="Failed to load user"
        onRetry={() => window.location.reload()}
      />
    );
  }

  if (!user) {
    return (
      <div className="user-edit-page">
        <p>User not found.</p>
        <Link to="/admin">Back to Admin</Link>
      </div>
    );
  }

  return (
    <div className="user-edit-page" data-testid="admin-user-edit-page">
      <div className="user-edit-header">
        <h1>Edit User</h1>
        <p className="user-edit-subtitle">
          {user.email} — {user.tenant_name ?? 'Unknown tenant'}
        </p>
      </div>

      <form className="user-edit-form" onSubmit={handleSubmit} data-testid="admin-user-edit-form">
        {updateMutation.isError && (
          <div className="user-edit-error" role="alert">
            {(updateMutation.error as Error)?.message ?? 'Failed to update user'}
          </div>
        )}

        <div className="user-edit-field">
          <label htmlFor="display_name">Display name</label>
          <input
            id="display_name"
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Display name"
          />
        </div>

        <div className="user-edit-field">
          <label htmlFor="status">Status</label>
          <select
            id="status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            {USER_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        <div className="user-edit-field">
          <label>Roles</label>
          {rolesLoading ? (
            <p className="user-edit-hint">Loading roles...</p>
          ) : roles && roles.length > 0 ? (
            <div className="user-edit-roles">
              {roles.map((role) => (
                <label key={role.id} className="user-edit-role-checkbox">
                  <input
                    type="checkbox"
                    checked={selectedRoleIds.has(role.id)}
                    onChange={() => handleRoleToggle(role.id)}
                  />
                  <span>{role.name}</span>
                </label>
              ))}
            </div>
          ) : (
            <p className="user-edit-hint">No roles available for this tenant.</p>
          )}
        </div>

        <div className="user-edit-actions">
          <button type="submit" disabled={updateMutation.isPending} data-testid="admin-user-edit-save">
            {updateMutation.isPending ? 'Saving...' : 'Save'}
          </button>
          <Link to="/admin" className="user-edit-cancel">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
