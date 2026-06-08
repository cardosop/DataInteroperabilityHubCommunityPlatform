/**
 * Provider Revenue Page — Phase 271.4.3
 *
 * Displays Stripe Connect payout history for the authenticated
 * provider tenant at route ``/settings/revenue``. Lists payouts in
 * reverse-chronological order and surfaces a warning banner when
 * any payout is in ``FAILED`` status.
 *
 * Data source: ``GET /api/v1/billing/connect/payouts/``
 * (paginated, 20 per page, ordered by ``-arrival_date``).
 */

import { useEffect, useState, useCallback } from 'react';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { Button } from '../../../shared/components/Button';
import { useTranslation } from '../../../shared/i18n/useTranslation';
import { formatCurrency, formatDate } from '../../../shared/i18n/formatters';
import './ProviderRevenuePage.css';

interface PayoutRecord {
  id: string;
  stripe_payout_id: string;
  amount_cents: number;
  currency: string;
  arrival_date: string;
  status: string;
  failure_code: string | null;
  failure_message: string | null;
  created_at: string;
}

interface PayoutsResponse {
  results: PayoutRecord[];
  count: number;
  page: number;
  page_size: number;
  num_pages: number;
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    PAID: 'Paid',
    PENDING: 'Pending',
    FAILED: 'Failed',
    IN_TRANSIT: 'In Transit',
    CANCELLED: 'Cancelled',
  };
  return map[status] ?? status;
}

export function ProviderRevenuePage() {
  const { t } = useTranslation();
  const [payouts, setPayouts] = useState<PayoutRecord[]>([]);
  const [page, setPage] = useState(1);
  const [numPages, setNumPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPayouts = useCallback(async (pageNum: number) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(
        `/api/v1/billing/connect/payouts/?page=${pageNum}&page_size=20`,
        { credentials: 'include' },
      );
      if (resp.status === 404) {
        setPayouts([]);
        setTotal(0);
        setNumPages(1);
        setError('no_connect_account');
        return;
      }
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const data: PayoutsResponse = await resp.json();
      setPayouts(data.results);
      setNumPages(data.num_pages);
      setTotal(data.count);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load payouts');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPayouts(page);
  }, [page, fetchPayouts]);

  const hasFailed = payouts.some((p) => p.status === 'FAILED');

  if (loading) return <LoadingSpinner data-testid="revenue-loading" />;
  if (error === 'no_connect_account') {
    return (
      <div className="provider-revenue-page" data-testid="provider-revenue-page">
        <h1>{t('billing.revenue.title')}</h1>
        <p>{t('billing.revenue.no_connect')}</p>
      </div>
    );
  }
  if (error) {
    return (
      <ErrorDisplay
        error={error}
        title="Failed to load revenue data"
        onRetry={() => fetchPayouts(page)}
      />
    );
  }

  return (
    <div className="provider-revenue-page" data-testid="provider-revenue-page">
      <h1>Provider Revenue</h1>

      {hasFailed && (
        <div
          role="alert"
          className="error-display payout-failed-banner"
          data-testid="payout-failed-banner"
        >
          <h3>One or more payouts have failed</h3>
          <p>
            Contact support if the issue persists. Check the Stripe
            Dashboard for detailed failure reasons.
          </p>
        </div>
      )}

      <p className="revenue-total" data-testid="revenue-total">
        Total payouts: {total}
      </p>

      {payouts.length === 0 ? (
        <p>No payouts yet.</p>
      ) : (
        <table className="payout-table" data-testid="payout-table">
          <thead>
            <tr>
              <th>Payout ID</th>
              <th>Amount</th>
              <th>Arrival Date</th>
              <th>Status</th>
              <th>Failure Info</th>
            </tr>
          </thead>
          <tbody>
            {payouts.map((p) => (
              <tr key={p.id} data-testid={`payout-row-${p.id}`}>
                <td>
                  <code>{p.stripe_payout_id}</code>
                </td>
                <td>{formatCurrency(p.amount_cents, p.currency)}</td>
                <td>{formatDate(p.arrival_date)}</td>
                <td>
                  <span className={`payout-status payout-status-${p.status.toLowerCase()}`}>
                    {statusLabel(p.status)}
                  </span>
                </td>
                <td>
                  {p.failure_code && (
                    <span className="payout-failure-code" data-testid={`failure-${p.id}`}>
                      {p.failure_code}
                      {p.failure_message ? `: ${p.failure_message}` : ''}
                    </span>
                  )}
                  {!p.failure_code && '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {numPages > 1 && (
        <div className="payout-pagination" data-testid="payout-pagination">
          <Button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            variant="secondary"
          >
            Previous
          </Button>
          <span>
            Page {page} of {numPages}
          </span>
          <Button
            onClick={() => setPage((p) => Math.min(numPages, p + 1))}
            disabled={page >= numPages}
            variant="secondary"
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
