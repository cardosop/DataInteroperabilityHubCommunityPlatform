/**
 * Phase 277.B.108 — shared ``PlanLimitErrorBanner`` for plan-limit-exceeded
 * errors with an inline "Upgrade Plan" CTA.
 *
 * Severity-coloured: yellow at >=80% quota, red at 100% (hard limit hit).
 * Accessible: aria-live=polite, aria-label on CTA link.
 */
import { useNavigate } from 'react-router-dom';
import type { FC } from 'react';
import './PlanLimitErrorBanner.css';

export interface PlanLimitErrorBannerProps {
  /** Human-readable resource name (e.g. "assets", "datasets"). */
  resourceLabel: string;
  /** Current usage count. */
  current: number;
  /** Plan limit (max). */
  max: number;
  /** Optional: user's current plan tier. */
  planTier?: string | null;
  /** Optional: additional detail message. */
  detail?: string;
  /** Optional test id. */
  'data-testid'?: string;
}

export const PlanLimitErrorBanner: FC<PlanLimitErrorBannerProps> = ({
  resourceLabel,
  current,
  max,
  planTier,
  detail,
  'data-testid': testId = 'plan-limit-error-banner',
}) => {
  const navigate = useNavigate();
  const pct = max > 0 ? Math.round((current / max) * 100) : 100;
  const severity = pct >= 100 ? 'critical' : pct >= 80 ? 'warning' : 'info';

  const bannerClass = `plan-limit-banner plan-limit-banner--${severity}`;

  return (
    <div
      className={bannerClass}
      role="alert"
      aria-live="polite"
      data-testid={testId}
    >
      <div className="plan-limit-banner__icon" aria-hidden="true">
        {severity === 'critical' ? '⛔' : severity === 'warning' ? '⚠️' : 'ℹ️'}
      </div>
      <div className="plan-limit-banner__body">
        <strong className="plan-limit-banner__title">
          {resourceLabel} quota reached ({current} / {max})
          {planTier ? ` — ${planTier} plan` : ''}
        </strong>
        {detail && <p className="plan-limit-banner__detail">{detail}</p>}
      </div>
      <a
        className="plan-limit-banner__cta"
        href="/settings/billing"
        onClick={(e) => {
          e.preventDefault();
          navigate('/settings/billing');
        }}
        aria-label={`Upgrade your plan to increase ${resourceLabel} limit`}
      >
        Upgrade Plan
      </a>
    </div>
  );
};
