/**
 * KYB Review Queue Page — Phase 271.5.2
 *
 * PLATFORM_ADMIN page at route ``/admin/connect/`` listing
 * ConnectAccounts stuck in Stripe's KYB pipeline >24h after
 * creation (details_submitted=True, charges_enabled=False).
 *
 * Data source: ``GET /api/v1/admin/connect/review-queue/``
 */

import { useEffect, useState, useCallback } from 'react';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import './KYBReviewQueuePage.css';

interface StuckAccount {
  id: string;
  stripe_account_id: string;
  tenant_id: string;
  tenant_name: string;
  country: string;
  details_submitted: boolean;
  charges_enabled: boolean;
  payouts_enabled: boolean;
  currently_due: string[];
  past_due: string[];
  created_at: string;
  hours_stuck: number;
}

interface ReviewQueueResponse {
  results: StuckAccount[];
  count: number;
}

export function KYBReviewQueuePage() {
  const [results, setResults] = useState<StuckAccount[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch('/api/v1/admin/connect/review-queue/', {
        credentials: 'include',
      });
      if (resp.status === 403) {
        setError('Platform admin access required.');
        setLoading(false);
        return;
      }
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const data: ReviewQueueResponse = await resp.json();
      setResults(data.results);
      setCount(data.count);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load review queue');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  if (loading) return <LoadingSpinner data-testid="kyb-queue-loading" />;
  if (error) {
    return (
      <ErrorDisplay
        error={error}
        title="KYB Review Queue"
        onRetry={fetchQueue}
      />
    );
  }

  return (
    <div className="kyb-review-queue-page" data-testid="kyb-review-queue-page">
      <h1>KYB Review Queue</h1>
      <p className="kyb-queue-summary">
        {count} account{count !== 1 ? 's' : ''} stuck in Stripe KYB pipeline
        {' (>24 hours since creation)'}
      </p>

      {results.length === 0 ? (
        <p className="kyb-queue-empty">No stuck accounts — queue is clear.</p>
      ) : (
        <table className="kyb-queue-table" data-testid="kyb-queue-table">
          <thead>
            <tr>
              <th>Stripe Account</th>
              <th>Tenant</th>
              <th>Country</th>
              <th>Hours Stuck</th>
              <th>Currently Due</th>
              <th>Past Due</th>
            </tr>
          </thead>
          <tbody>
            {results.map((acct) => (
              <tr key={acct.id} data-testid={`kyb-row-${acct.id}`}>
                <td>
                  <code>{acct.stripe_account_id}</code>
                </td>
                <td>{acct.tenant_name}</td>
                <td>{acct.country}</td>
                <td>
                  <span
                    className={`kyb-stuck-hours ${
                      acct.hours_stuck > 72 ? 'kyb-critical' : ''
                    }`}
                  >
                    {acct.hours_stuck}h
                  </span>
                </td>
                <td>
                  {acct.currently_due.length > 0
                    ? acct.currently_due.join(', ')
                    : '-'}
                </td>
                <td>
                  {acct.past_due.length > 0
                    ? acct.past_due.join(', ')
                    : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
