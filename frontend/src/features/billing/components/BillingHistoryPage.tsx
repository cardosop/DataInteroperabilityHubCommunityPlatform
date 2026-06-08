/**
 * 285.13.11.5 — Billing History Page (RC25).
 *
 * Invoice list with amounts, status badges, period dates, PDF links,
 * labeled by subscription category (BASE / ML_AI).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { apiClient } from '../../../shared/api/client';
import type { Invoice } from '../../../shared/types/billing';

const BASE = '/api/v1';

function statusLabel(status: Invoice['status']): string {
  const map: Record<string, string> = {
    paid: 'Paid', open: 'Open', draft: 'Draft',
    uncollectible: 'Uncollectible', void: 'Void',
  };
  return map[status] || status;
}

export const BillingHistoryPage: React.FC = () => {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchInvoices = useCallback(async () => {
    try {
      setLoading(true);
      const resp = await apiClient.getClient().get<Invoice[]>(
        `${BASE}/billing/invoices/`,
      );
      setInvoices(resp.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load invoices');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchInvoices(); }, [fetchInvoices]);

  if (loading) return <div role="status">Loading billing history…</div>;
  if (error) return <div role="alert">{error}</div>;

  return (
    <div className="billing-history">
      <h1>Billing History</h1>
      {invoices.length === 0 ? (
        <p>No invoices yet.</p>
      ) : (
        <table className="billing-history__table" role="table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Amount</th>
              <th>Status</th>
              <th>Category</th>
              <th>Period</th>
              <th>Invoice</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((inv) => (
              <tr key={inv.id}>
                <td>{inv.period_start ? new Date(inv.period_start).toLocaleDateString() : '—'}</td>
                <td>
                  ${((inv.amount_due_cents || 0) / 100).toFixed(2)}{' '}
                  {inv.currency?.toUpperCase()}
                </td>
                <td>
                  <span className={`badge badge--${inv.status}`} aria-label={`Status: ${statusLabel(inv.status)}`}>
                    {statusLabel(inv.status)}
                  </span>
                </td>
                <td>
                  <span className={`badge badge--category`}>
                    {inv.category || 'BASE'}
                  </span>
                </td>
                <td>
                  {inv.period_start && inv.period_end
                    ? `${new Date(inv.period_start).toLocaleDateString()} – ${new Date(inv.period_end).toLocaleDateString()}`
                    : '—'}
                </td>
                <td>
                  {inv.invoice_pdf_url ? (
                    <a href={inv.invoice_pdf_url} target="_blank" rel="noopener noreferrer" aria-label={`Download PDF invoice for ${new Date(inv.period_start!).toLocaleDateString()}`}>
                      PDF
                    </a>
                  ) : inv.hosted_invoice_url ? (
                    <a href={inv.hosted_invoice_url} target="_blank" rel="noopener noreferrer">
                      View
                    </a>
                  ) : (
                    '—'
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};
