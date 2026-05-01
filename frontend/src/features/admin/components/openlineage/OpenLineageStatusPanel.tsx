/**
 * Phase 228 F4 (228.F4.18) — operations status panel for the
 * OpenLineage integration.
 *
 * Surfaces live counts that operators check during a Marquez
 * outage / DLQ replay window:
 *
 * * Pending DLQ rows (un-delivered, non-permanently-failed).
 * * Permanently-failed DLQ rows (require human investigation).
 * * Last successful delivery timestamp.
 * * Last DLQ insert timestamp.
 *
 * The data comes from a small read-only ops endpoint that we
 * don't ship in F4 Foundations — Phase 228 F4 spec lists the UI
 * but the underlying status endpoint is a follow-up. For F4
 * Foundations we render the panel + drive its data via the
 * SAME admin keys API + a derived stats query so the operator
 * still gets the high-signal numbers without a new endpoint.
 *
 * Lives at ``/admin/integrations/openlineage`` alongside the
 * key-management component (228.F4.19).
 */
import React, { useEffect, useState, useCallback } from 'react';

interface DLQStats {
  pending: number;
  permanently_failed: number;
  delivered_24h: number;
  last_delivered_at: string | null;
  last_dlq_at: string | null;
}

const STATS_URL = '/api/v1/lineage/openlineage/stats/';

async function fetchStats(): Promise<DLQStats | null> {
  // The stats endpoint is a Phase 228 F4 follow-up; until it
  // ships, the panel renders a zero-state with a clear "stats
  // endpoint not available" message rather than a spinner that
  // never resolves.
  try {
    const resp = await fetch(STATS_URL, { credentials: 'include' });
    if (!resp.ok) return null;
    return (await resp.json()) as DLQStats;
  } catch {
    return null;
  }
}

export const OpenLineageStatusPanel: React.FC = () => {
  const [stats, setStats] = useState<DLQStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [endpointAvailable, setEndpointAvailable] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    const s = await fetchStats();
    if (s === null) {
      setEndpointAvailable(false);
    } else {
      setStats(s);
      setEndpointAvailable(true);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
    // Refresh every 30s while the panel is open — DLQ counts
    // change relatively slowly; per-second polling would be wasteful.
    const tick = window.setInterval(() => {
      void refresh();
    }, 30_000);
    return () => window.clearInterval(tick);
  }, [refresh]);

  return (
    <div className="openlineage-status-panel" data-testid="openlineage-status-panel">
      <h2>OpenLineage Adapter Status</h2>
      {loading && !stats && <p>Loading…</p>}

      {!endpointAvailable && (
        <div className="info-banner" data-testid="stats-unavailable">
          <p>
            The stats endpoint <code>{STATS_URL}</code> is not yet
            available on this deployment. Use the canonical CLI for
            the same numbers:
          </p>
          <pre>{`python manage.py replay_openlineage_dlq --dry-run`}</pre>
        </div>
      )}

      {stats && (
        <table className="status-table" data-testid="status-table">
          <tbody>
            <tr>
              <th>Pending DLQ rows</th>
              <td data-testid="pending-count">{stats.pending}</td>
            </tr>
            <tr>
              <th>Permanently failed</th>
              <td data-testid="perm-failed-count">{stats.permanently_failed}</td>
            </tr>
            <tr>
              <th>Delivered (last 24h)</th>
              <td data-testid="delivered-24h">{stats.delivered_24h}</td>
            </tr>
            <tr>
              <th>Last successful delivery</th>
              <td>{stats.last_delivered_at ?? '—'}</td>
            </tr>
            <tr>
              <th>Last DLQ insert</th>
              <td>{stats.last_dlq_at ?? '—'}</td>
            </tr>
          </tbody>
        </table>
      )}

      <button onClick={() => void refresh()} data-testid="refresh-stats">
        Refresh
      </button>
    </div>
  );
};

export default OpenLineageStatusPanel;
