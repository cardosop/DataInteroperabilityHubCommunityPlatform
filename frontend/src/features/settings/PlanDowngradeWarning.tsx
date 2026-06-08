/**
 * 285.13.11.4 — Plan downgrade warning component.
 */
import React from 'react';
import type { PlanPricing } from '../../shared/types/billing';

export interface PlanDowngradeWarningProps {
  currentPlan: PlanPricing;
  targetPlan: PlanPricing;
  exceededLimits: string[];
  onConfirm: () => void;
  onCancel: () => void;
}

export const PlanDowngradeWarning: React.FC<PlanDowngradeWarningProps> = ({
  currentPlan, targetPlan, exceededLimits, onConfirm, onCancel,
}) => (
  <div className="dialog-overlay" role="dialog" aria-modal="true" aria-label="Downgrade warning">
    <div className="dialog">
      <h2>Downgrade to {targetPlan.name}?</h2>
      <p>
        You are about to downgrade from <strong>{currentPlan.name}</strong> to{' '}
        <strong>{targetPlan.name}</strong>. Your new limits take effect at the
        end of the current billing period.
      </p>
      {exceededLimits.length > 0 && (
        <div className="dialog__warning" role="alert">
          <strong>Warning:</strong> Your current usage exceeds the new plan limits for:
          <ul>
            {exceededLimits.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
          Please reduce usage before the period ends to avoid service interruption.
        </div>
      )}
      <div className="dialog__actions">
        <button onClick={onCancel} className="btn--secondary">Cancel</button>
        <button onClick={onConfirm} className="btn--danger">Confirm Downgrade</button>
      </div>
    </div>
  </div>
);
