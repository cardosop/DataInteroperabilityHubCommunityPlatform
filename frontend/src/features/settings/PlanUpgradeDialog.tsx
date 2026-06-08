/**
 * 285.13.11.4 — Plan upgrade confirmation dialog with proration note (RC23).
 */
import React from 'react';
import type { PlanPricing } from '../../shared/types/billing';

export interface PlanUpgradeDialogProps {
  open: boolean;
  currentPlan: PlanPricing;
  targetPlan: PlanPricing;
  loading: boolean;
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

export const PlanUpgradeDialog: React.FC<PlanUpgradeDialogProps> = ({
  open, currentPlan, targetPlan, loading, error, onConfirm, onCancel,
}) => {
  if (!open) return null;

  const priceDiff = targetPlan.price_amount_cents - currentPlan.price_amount_cents;

  return (
    <div className="dialog-overlay" role="dialog" aria-modal="true" aria-label="Confirm plan upgrade">
      <div className="dialog">
        <h2>Upgrade to {targetPlan.name}</h2>
        <p>
          You are upgrading from <strong>{currentPlan.name}</strong> to{' '}
          <strong>{targetPlan.name}</strong>.
        </p>
        <p className="proration-note">
          Your card will be charged the prorated difference of{' '}
          <strong>${(priceDiff / 100).toFixed(2)}</strong> for the remainder
          of this billing period. Your new limits take effect immediately.
        </p>

        {error && (
          <div className="dialog__error" role="alert">
            {error}
          </div>
        )}

        <div className="dialog__actions">
          <button onClick={onCancel} disabled={loading} className="btn--secondary">
            Cancel
          </button>
          <button onClick={onConfirm} disabled={loading} className="btn--primary">
            {loading ? 'Processing…' : `Upgrade — $${(priceDiff / 100).toFixed(2)}`}
          </button>
        </div>
      </div>
    </div>
  );
};
