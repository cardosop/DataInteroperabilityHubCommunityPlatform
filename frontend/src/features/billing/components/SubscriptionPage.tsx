/**
 * Subscription Page
 * Displays plan, status, limits, plan change, and invoice history for tenant admin.
 * Route: /settings/subscription
 */

import { useState } from 'react';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import {
  useChangePlan,
  useCurrentSubscription,
  useInvoices,
  usePlans,
} from '../hooks/useSubscription';
import type { Invoice } from '../services/billingService';
import './SubscriptionPage.css';

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return '—';
  }
}

function formatLimitKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatCurrency(amount: string, currency: string): string {
  const num = parseFloat(amount);
  if (Number.isNaN(num)) return amount;
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: currency.toUpperCase(),
  }).format(num);
}

export function SubscriptionPage() {
  const { data: subscription, isLoading, error, refetch } = useCurrentSubscription();
  const { data: plans = [], isLoading: plansLoading } = usePlans();
  const { data: invoices = [], isLoading: invoicesLoading } = useInvoices();
  const changePlanMutation = useChangePlan();
  const [selectedPlanSlug, setSelectedPlanSlug] = useState<string>('');

  if (isLoading && !subscription) {
    return <LoadingSpinner message="Loading subscription..." />;
  }

  if (error) {
    return (
      <ErrorDisplay
        error={error as Error}
        title="Failed to load subscription"
        onRetry={() => refetch()}
      />
    );
  }

  if (!subscription) {
    return (
      <div className="subscription-page">
        <h1>Subscription</h1>
        <p className="subscription-no-data">No subscription found for your tenant.</p>
      </div>
    );
  }

  const limits = subscription.limits ?? {};
  const limitEntries = Object.entries(limits);
  const otherPlans = plans.filter((p) => p.slug !== subscription.plan_slug);
  const changePlanError = changePlanMutation.error as Error & { response?: { data?: { error?: string } } };
  const changePlanErrorMessage =
    changePlanError?.response?.data?.error ?? changePlanError?.message;

  const handleChangePlan = () => {
    if (!selectedPlanSlug) return;
    changePlanMutation.mutate(selectedPlanSlug, {
      onSuccess: () => setSelectedPlanSlug(''),
    });
  };

  return (
    <div className="subscription-page">
      <div className="subscription-page-header">
        <h1>Subscription</h1>
        <p className="subscription-page-description">
          Your current plan, status, resource limits, and invoice history.
        </p>
      </div>

      <section className="subscription-card" aria-labelledby="subscription-plan-heading">
        <h2 id="subscription-plan-heading">Plan</h2>
        <dl className="subscription-dl">
          <dt>Plan name</dt>
          <dd>{subscription.plan_name}</dd>
          <dt>Plan tier</dt>
          <dd>
            <span className={`subscription-badge subscription-tier-${subscription.plan_tier?.toLowerCase()}`}>
              {subscription.plan_tier}
            </span>
          </dd>
          <dt>Status</dt>
          <dd>
            <span className={`subscription-badge subscription-status-${subscription.status?.toLowerCase()}`}>
              {subscription.status}
            </span>
          </dd>
          <dt>Current period</dt>
          <dd>
            {formatDate(subscription.current_period_start)} – {formatDate(subscription.current_period_end)}
          </dd>
          {subscription.trial_end && (
            <>
              <dt>Trial ends</dt>
              <dd>{formatDate(subscription.trial_end)}</dd>
            </>
          )}
          {subscription.cancel_at_period_end && (
            <>
              <dt>Cancellation</dt>
              <dd>Cancels at end of period</dd>
            </>
          )}
        </dl>

        {otherPlans.length > 0 && (
          <div className="subscription-change-plan">
            <h3>Change plan</h3>
            <div className="subscription-change-plan-controls">
              <select
                value={selectedPlanSlug}
                onChange={(e) => setSelectedPlanSlug(e.target.value)}
                disabled={plansLoading || changePlanMutation.isPending}
                aria-label="Select plan to switch to"
              >
                <option value="">Select a plan…</option>
                {otherPlans.map((p) => (
                  <option key={p.id} value={p.slug}>
                    {p.name} ({p.tier})
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={handleChangePlan}
                disabled={!selectedPlanSlug || changePlanMutation.isPending}
                className="subscription-change-plan-btn"
              >
                {changePlanMutation.isPending ? 'Changing…' : 'Change plan'}
              </button>
            </div>
            {changePlanErrorMessage && (
              <p className="subscription-change-plan-error" role="alert">
                {changePlanErrorMessage}
              </p>
            )}
          </div>
        )}
      </section>

      {limitEntries.length > 0 && (
        <section className="subscription-card" aria-labelledby="subscription-limits-heading">
          <h2 id="subscription-limits-heading">Limits</h2>
          <dl className="subscription-dl subscription-limits">
            {limitEntries.map(([key, value]) => (
              <div key={key} className="subscription-limit-row">
                <dt>{formatLimitKey(key)}</dt>
                <dd>{typeof value === 'number' ? value.toLocaleString() : String(value)}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      <section className="subscription-card" aria-labelledby="subscription-invoices-heading">
        <h2 id="subscription-invoices-heading">Invoice history</h2>
        {invoicesLoading ? (
          <p className="subscription-invoices-loading">Loading invoices…</p>
        ) : invoices.length === 0 ? (
          <p className="subscription-no-data">No invoices yet.</p>
        ) : (
          <table className="subscription-invoices-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Download</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv: Invoice) => (
                <tr key={inv.id}>
                  <td>{formatDate(inv.created_at)}</td>
                  <td>{formatCurrency(inv.amount_due, inv.currency)}</td>
                  <td>
                    <span className={`subscription-badge subscription-status-${inv.status?.toLowerCase()}`}>
                      {inv.status}
                    </span>
                  </td>
                  <td>
                    {(inv.invoice_pdf_url || inv.hosted_invoice_url) ? (
                      <a
                        href={inv.invoice_pdf_url ?? inv.hosted_invoice_url ?? '#'}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {inv.invoice_pdf_url ? 'PDF' : 'View'}
                      </a>
                    ) : (
                      <span className="subscription-invoice-no-download">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
