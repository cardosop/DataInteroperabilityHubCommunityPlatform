/**
 * Phase 227 Wave 1 (227.L5.8) — TENANT_ADMIN contract-health triage page.
 *
 * Lists every contract in the tenant flagged as structureless by the
 * backend (``GET /api/v1/contracts/?filter=structureless``) so admins
 * can locate offenders and deep-link straight into the Schema editor.
 *
 * Permissions: TENANT_ADMIN-only. The role check is a permission gate
 * (not a feature flag) and stays per the 2026-04-30 ungate directive —
 * we ungated the *visibility/feature flag*, but role-based authorisation
 * is a separate concern that remains.
 */
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { contractService } from '../../contracts/services/contractService';
import type { Contract } from '../../../shared/types/contracts';

export function ContractHealthPage() {
  const [data, setData] = useState<Contract[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    // ``contractService.list`` accepts a typed filter set; we cast the
    // ``filter`` extension below since the existing TypeScript shape
    // doesn't yet include a ``filter`` member. The backend filter is
    // tenant-scoped at the queryset layer.
    contractService
      .list({ filter: 'structureless' } as unknown as Parameters<typeof contractService.list>[0])
      .then((page) => {
        if (cancelled) return;
        setData(page.results);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const rows = useMemo(() => data ?? [], [data]);

  if (loading) return <LoadingSpinner message="Scanning contracts…" />;
  if (error) return <ErrorDisplay error={error} title="Failed to load contract health" />;

  if (rows.length === 0) {
    return (
      <div className="contract-health-page" data-testid="contract-health-page">
        <h2>Contract health</h2>
        <EmptyState
          data-testid="contract-health-empty"
          title="No structureless contracts"
          message="Every contract in this tenant has at least one model with fields, or top-level schema fields. Nothing to triage."
        />
      </div>
    );
  }

  return (
    <div className="contract-health-page" data-testid="contract-health-page">
      <header>
        <h2>Contract health</h2>
        <p>
          {rows.length} contract{rows.length === 1 ? '' : 's'} have no resolvable
          models or schema fields. Open the Schema editor on each to add structure.
        </p>
      </header>

      <table className="contract-health-table" data-testid="contract-health-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Spec</th>
            <th>Spec version</th>
            <th>Status</th>
            <th>Updated</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id} data-testid={`contract-health-row-${c.id}`}>
              <td>
                <Link to={`/contracts/${c.id}`} data-testid={`contract-link-${c.id}`}>
                  {c.name ?? c.id}
                </Link>
              </td>
              <td>{c.original_spec_type ?? '—'}</td>
              <td>
                {(c as unknown as { original_spec_version?: string }).original_spec_version ?? '—'}
              </td>
              <td>{c.status ?? '—'}</td>
              <td>
                {c.updated_at ? new Date(c.updated_at).toLocaleString() : '—'}
              </td>
              <td>
                <Link
                  to={`/contracts/${c.id}/edit?tab=schema`}
                  data-testid={`contract-fix-${c.id}`}
                >
                  Open Schema editor
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
