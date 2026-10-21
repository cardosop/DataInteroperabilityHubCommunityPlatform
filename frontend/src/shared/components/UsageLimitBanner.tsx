/**
 * 285.13.11.6 — Usage Limit Banner.
 *
 * Yellow (≥80%), orange (≥95%), red (≥100%). Shows the specific resource
 * at threshold. Links to plan settings. Dismissible per resource per session.
 * a11y: ``role="progressbar"`` on the usage bar (285.13.11.8).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

export interface UsageLimitBannerProps {
  limitKey: string;
  displayName: string;
  usage: number;
  limit: number | null;
  percentage: number;
  status: 'warning' | 'critical' | 'exceeded';
}

const STATUS_STYLES: Record<string, { bg: string; bar: string }> = {
  warning:  { bg: 'banner--yellow', bar: 'usage-bar__fill--warning' },
  critical: { bg: 'banner--orange', bar: 'usage-bar__fill--critical' },
  exceeded: { bg: 'banner--red',   bar: 'usage-bar__fill--exceeded' },
};

const STORAGE_KEY = 'dismissed_usage_banners';

function getDismissed(): Set<string> {
  try {
    return new Set(JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]'));
  } catch { return new Set(); }
}
function setDismissed(set: Set<string>) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify([...set]));
}

export const UsageLimitBanner: React.FC<UsageLimitBannerProps> = ({
  limitKey, displayName, usage, limit, percentage, status,
}) => {
  const [dismissed, setDismissedState] = useState(false);
  const navigate = useNavigate();
  const style = STATUS_STYLES[status] || STATUS_STYLES.warning;

  useEffect(() => {
    if (getDismissed().has(limitKey)) setDismissedState(true);
  }, [limitKey]);

  const handleDismiss = useCallback(() => {
    const d = getDismissed();
    d.add(limitKey);
    setDismissed(d);
    setDismissedState(true);
  }, [limitKey]);

  if (dismissed) return null;
  if (percentage === null || percentage === undefined || (limit !== null && percentage < 80)) return null;

  return (
    <div className={`usage-limit-banner ${style.bg}`} role="alert">
      <div className="usage-limit-banner__content">
        <strong>{displayName}:</strong>{' '}
        {usage.toLocaleString()} / {limit?.toLocaleString() ?? '∞'} ({percentage.toFixed(0)}%)
      </div>
      <div
        className="usage-limit-banner__bar"
        role="progressbar"
        aria-valuenow={Math.min(percentage, 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${displayName} usage: ${percentage.toFixed(0)}%`}
      >
        <div
          className={`usage-bar__fill ${style.bar}`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
      <div className="usage-limit-banner__actions">
        <button onClick={() => navigate('/settings/plan')}>
          Manage Plan
        </button>
        <button onClick={handleDismiss} aria-label={`Dismiss ${displayName} warning`}>
          Dismiss
        </button>
      </div>
    </div>
  );
};
