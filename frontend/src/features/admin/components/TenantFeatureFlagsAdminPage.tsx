/**
 * Phase 250.6.E.1 — per-tenant feature-flags admin page.
 *
 * Route: ``/admin/tenant-settings/`` (registered in
 * `frontend/src/app/routes/routes.tsx` behind a
 * ``<ProtectedRoute requiredRole={['TENANT_ADMIN', 'PLATFORM_ADMIN']}>``
 * gate per Phase 250.6.E.2).
 *
 * UX contract:
 *
 *  1. Render every per-tenant capability flag the backend exposes,
 *     with its description + current value + a toggle. The flag
 *     list is BACKEND-DRIVEN (returned by
 *     ``GET /me/feature-flags/``) so adding a new flag on the
 *     backend's `_TENANT_FEATURE_FLAGS` tuple lights it up here
 *     without touching the FE.
 *
 *  2. Below the form, render the audit-log history (10 most-recent
 *     ``TENANT_FEATURE_FLAG_UPDATED`` events) so the admin sees
 *     "who changed what when" co-located with the action.
 *
 *  3. Each toggle commits via PATCH on change — no global
 *     "Save" button. The backend gate is the source of truth;
 *     reconciling the SPA's optimistic state with the server's
 *     authoritative response avoids the half-saved state that
 *     a Save-button form invites.
 *
 *  4. On error (403 / 500 / network), surface a structured
 *     ErrorDisplay with a Retry button. NEVER silently revert
 *     the toggle — the user should see what they tried + what
 *     went wrong.
 */
import { useEffect, useState } from 'react';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { ApiError } from '../../../shared/types/api';
import { normalizeError } from '../../../shared/utils/errorUtils';
import {
  tenantService,
  type TenantFeatureFlag,
  type TenantFeatureFlagHistoryEvent,
} from '../../tenants/services/tenantService';

const BREADCRUMBS = [
  { label: 'Home', href: '/' },
  { label: 'Admin', href: '/admin' },
  { label: 'Tenant Settings' },
];

export function TenantFeatureFlagsAdminPage() {
  const [flags, setFlags] = useState<TenantFeatureFlag[]>([]);
  const [history, setHistory] = useState<TenantFeatureFlagHistoryEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingFlag, setSavingFlag] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const loadAll = async () => {
    setError(null);
    setLoading(true);
    try {
      const [flagsResp, historyResp] = await Promise.all([
        tenantService.getMeFeatureFlags(),
        tenantService.getMeFeatureFlagHistory(),
      ]);
      setFlags(flagsResp.flags);
      setHistory(historyResp.events);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAll();
  }, []);

  const handleToggle = async (flagName: string, newValue: boolean) => {
    setSavingFlag(flagName);
    setError(null);
    try {
      const resp = await tenantService.patchMeFeatureFlags({
        [flagName]: newValue,
      });
      setFlags(resp.flags);
      // Reload the audit history so the new event appears.
      const historyResp = await tenantService.getMeFeatureFlagHistory();
      setHistory(historyResp.events);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setSavingFlag(null);
    }
  };

  if (loading) {
    return (
      <main
        className="tenant-feature-flags-admin-page"
        data-testid="tenant-feature-flags-admin-page-loading"
      >
        <LoadingSpinner message="Loading tenant settings…" />
      </main>
    );
  }

  return (
    <main
      className="tenant-feature-flags-admin-page"
      data-testid="tenant-feature-flags-admin-page"
    >
      <Breadcrumbs items={BREADCRUMBS} />
      <header>
        <h1>Tenant Settings</h1>
        <p className="subtitle">
          Per-tenant capability flags for this tenant. Changes take
          effect immediately and are recorded in the audit log below.
        </p>
      </header>

      {error && (
        <ErrorDisplay
          error={error}
          title="Could not load or save tenant settings"
          onRetry={loadAll}
        />
      )}

      <section
        className="tenant-feature-flags-list"
        data-testid="tenant-feature-flags-list"
      >
        {flags.length === 0 && !error && (
          <p className="empty-state">No tenant feature flags configured.</p>
        )}
        {flags.map((flag) => (
          <div
            key={flag.name}
            className="tenant-feature-flag-row"
            data-testid={`tenant-feature-flag-row-${flag.name}`}
          >
            <div className="tenant-feature-flag-row__header">
              <label
                className="tenant-feature-flag-row__label"
                htmlFor={`flag-toggle-${flag.name}`}
              >
                <strong>{flag.name}</strong>
              </label>
              <input
                id={`flag-toggle-${flag.name}`}
                type="checkbox"
                checked={flag.value}
                disabled={savingFlag === flag.name}
                onChange={(e) =>
                  handleToggle(flag.name, e.currentTarget.checked)
                }
                data-testid={`tenant-feature-flag-toggle-${flag.name}`}
              />
            </div>
            <p className="tenant-feature-flag-row__description">
              {flag.description}
            </p>
          </div>
        ))}
      </section>

      <section
        className="tenant-feature-flag-history"
        data-testid="tenant-feature-flag-history"
      >
        <h2>Recent Changes</h2>
        {history.length === 0 ? (
          <p className="empty-state">
            No flag changes recorded yet. Changes you make above will
            appear here.
          </p>
        ) : (
          <ul>
            {history.slice(0, 10).map((ev) => (
              <li key={ev.id} data-testid={`history-event-${ev.id}`}>
                <time dateTime={ev.created_at}>
                  {new Date(ev.created_at).toLocaleString()}
                </time>
                {' — '}
                <code>{ev.details_json.flag_name ?? '(unknown)'}</code>
                {' '}
                changed from{' '}
                <code>{String(ev.details_json.previous_value)}</code>
                {' to '}
                <code>{String(ev.details_json.new_value)}</code>
                {ev.actor_user_id && (
                  <>
                    {' by user '}
                    <code>{ev.actor_user_id.slice(0, 8)}…</code>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
