/**
 * Subscription Page
 * Displays plan, status, limits, plan change with confirmation, and invoice history.
 * Route: /settings/subscription
 */

import { useState } from 'react';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import {
  useChangePlan,
  useCurrentSubscription,
  useInvoices,
  useMLSubscription,
  usePlans,
} from '../hooks/useSubscription';
import { billingService } from '../services/billingService';
import type { Invoice, TenantPlan } from '../services/billingService';
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

function formatLimitValue(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'Unlimited';
  return value.toLocaleString();
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
  const { data: mlSubscription } = useMLSubscription();
  const changePlanMutation = useChangePlan();
  const [selectedPlanSlug, setSelectedPlanSlug] = useState<string>('');
  const [confirmOpen, setConfirmOpen] = useState(false);

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
  const baseLimits = Object.entries(limits).filter(([k]) => !k.startsWith('max_ml_'));
  const mlLimits = Object.entries(limits).filter(([k]) => k.startsWith('max_ml_'));
  const otherPlans = plans.filter((p) => p.slug !== subscription.plan_slug);
  const selectedPlan = plans.find((p) => p.slug === selectedPlanSlug);

  const handleChangePlanClick = () => {
    if (!selectedPlanSlug) return;
    setConfirmOpen(true);
  };

  const handleConfirmChange = () => {
    setConfirmOpen(false);
    changePlanMutation.mutate(selectedPlanSlug, {
      onSuccess: () => setSelectedPlanSlug(''),
    });
  };

  // Build confirmation message
  const confirmMessage = selectedPlan
    ? `Change from ${subscription.plan_name} to ${selectedPlan.name}? ` +
      `Your billing will be updated and resource limits will change immediately.`
    : 'Are you sure you want to change your plan?';

  // Determine if downgrade (for warning variant)
  const isDowngrade = selectedPlan
    ? (selectedPlan.order ?? 0) < (plans.find((p) => p.slug === subscription.plan_slug)?.order ?? 0)
    : false;

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
                onClick={handleChangePlanClick}
                disabled={!selectedPlanSlug || changePlanMutation.isPending}
                className="subscription-change-plan-btn"
              >
                {changePlanMutation.isPending ? 'Changing…' : 'Change plan'}
              </button>
            </div>
            <div aria-live="polite" aria-atomic="true">
              {changePlanMutation.isError && (
                <p className="subscription-change-plan-error" role="alert">
                  {(changePlanMutation.error as Error)?.message ?? 'Failed to change plan'}
                </p>
              )}
              {changePlanMutation.isSuccess && (
                <p className="subscription-change-plan-success" role="status">
                  Plan changed successfully.
                </p>
              )}
            </div>
          </div>
        )}
      </section>

      {/* Plan comparison table (when a target plan is selected) */}
      {selectedPlan && (
        <PlanComparisonTable
          currentPlan={subscription.plan_name}
          currentLimits={limits}
          targetPlan={selectedPlan}
        />
      )}

      {baseLimits.length > 0 && (
        <section className="subscription-card" aria-labelledby="subscription-limits-heading">
          <h2 id="subscription-limits-heading">Limits</h2>
          <p className="subscription-section-label">Base Plan Limits</p>
          <dl className="subscription-dl subscription-limits">
            {baseLimits.map(([key, value]) => (
              <div key={key} className="subscription-limit-row">
                <dt>{formatLimitKey(key)}</dt>
                <dd>{formatLimitValue(value)}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {(mlSubscription || mlLimits.length > 0) && (
        <section className="subscription-card subscription-ml-addon" aria-labelledby="subscription-ml-heading">
          <h2 id="subscription-ml-heading">ML Add-on</h2>
          {mlSubscription && (
            <dl className="subscription-dl">
              <dt>Plan name</dt>
              <dd>{mlSubscription.plan_name}</dd>
              <dt>Status</dt>
              <dd>
                <span className={`subscription-badge subscription-status-${mlSubscription.status?.toLowerCase()}`}>
                  {mlSubscription.status}
                </span>
              </dd>
              {mlSubscription.current_period_start && (
                <>
                  <dt>Current period</dt>
                  <dd>
                    {formatDate(mlSubscription.current_period_start)} – {formatDate(mlSubscription.current_period_end)}
                  </dd>
                </>
              )}
            </dl>
          )}
          {mlLimits.length > 0 && (
            <>
              <p className="subscription-section-label">ML Limits</p>
              <dl className="subscription-dl subscription-limits">
                {mlLimits.map(([key, value]) => (
                  <div key={key} className="subscription-limit-row">
                    <dt>{formatLimitKey(key)}</dt>
                    <dd>{formatLimitValue(value)}</dd>
                  </div>
                ))}
              </dl>
            </>
          )}
        </section>
      )}

      <section className="subscription-card" aria-labelledby="subscription-invoices-heading">
        <h2 id="subscription-invoices-heading">Invoice history</h2>
        {invoicesLoading ? (
          <p className="subscription-invoices-loading" aria-busy="true">Loading invoices…</p>
        ) : invoices.length === 0 ? (
          <p className="subscription-no-data">No invoices yet.</p>
        ) : (
          <table className="subscription-invoices-table" aria-label="Invoice history">
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Period</th>
                <th scope="col">Amount</th>
                <th scope="col">Status</th>
                <th scope="col">Download</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv: Invoice) => (
                <tr key={inv.id}>
                  <td>{formatDate(inv.created_at)}</td>
                  <td>
                    {inv.period_start || inv.period_end
                      ? `${formatDate(inv.period_start)} – ${formatDate(inv.period_end)}`
                      : '—'}
                  </td>
                  <td>{formatCurrency(inv.amount_due, inv.currency)}</td>
                  <td>
                    <span className={`subscription-badge subscription-status-${inv.status?.toLowerCase()}`}>
                      {inv.status}
                    </span>
                  </td>
                  <td>
                    <a
                      href={billingService.getInvoiceDownloadUrl(inv.id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={`Download invoice from ${formatDate(inv.created_at)}`}
                    >
                      Download
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Confirmation dialog for plan change */}
      <ConfirmDialog
        isOpen={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={handleConfirmChange}
        title="Confirm plan change"
        message={confirmMessage}
        confirmLabel="Change plan"
        cancelLabel="Cancel"
        variant={isDowngrade ? 'warning' : 'info'}
      />
    </div>
  );
}


/**
 * Plan comparison table showing current vs target limits side-by-side.
 */
function PlanComparisonTable({
  currentPlan,
  currentLimits,
  targetPlan,
}: {
  currentPlan: string;
  currentLimits: Record<string, number | null>;
  targetPlan: TenantPlan;
}) {
  const targetLimits = targetPlan.limits_json ?? {};
  const allKeys = Array.from(
    new Set([...Object.keys(currentLimits), ...Object.keys(targetLimits)])
  ).sort();

  if (allKeys.length === 0) return null;

  return (
    <section className="subscription-card" aria-labelledby="plan-comparison-heading">
      <h2 id="plan-comparison-heading">Plan comparison</h2>
      <table className="subscription-comparison-table" aria-label="Plan limit comparison">
        <thead>
          <tr>
            <th scope="col">Limit</th>
            <th scope="col">{currentPlan}</th>
            <th scope="col">{targetPlan.name}</th>
            <th scope="col">Change</th>
          </tr>
        </thead>
        <tbody>
          {allKeys.map((key) => {
            const current = currentLimits[key] ?? null;
            const target = targetLimits[key] ?? null;
            const decreased =
              current !== null && target !== null && target < current;
            const increased =
              current !== null && target !== null && target > current;
            const toUnlimited = current !== null && target === null;

            return (
              <tr key={key} className={decreased ? 'comparison-decrease' : ''}>
                <td>{formatLimitKey(key)}</td>
                <td>{formatLimitValue(current)}</td>
                <td>{formatLimitValue(target)}</td>
                <td>
                  {decreased && <span className="comparison-badge comparison-down">Decrease</span>}
                  {increased && <span className="comparison-badge comparison-up">Increase</span>}
                  {toUnlimited && <span className="comparison-badge comparison-up">Unlimited</span>}
                  {!decreased && !increased && !toUnlimited && '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
