/**
 * Phase 260.4.G — file-storage quota meter for FileListPage.
 *
 * Severity colours (per spec):
 *   - <80%   → green / neutral
 *   - >80%   → yellow ("warning")
 *   - >95%   → red ("danger")
 *
 * "Upgrade for more" CTA appears when usage exceeds 90% — the
 * spec's threshold for nudging users toward a plan upgrade BEFORE
 * the limit-gate 403 starts blocking uploads.
 *
 * Render contract:
 *   - Loading → small inline skeleton (no full-page block; the meter
 *     mounts above the file list and shouldn't block its render).
 *   - Error   → silent (debug-only). The meter is a hint surface;
 *     hiding it on error degrades gracefully rather than wallpapering
 *     the page with red.
 *   - Unlimited → "Storage: X used (unlimited plan)" pill, no bar.
 *   - Capped (the common case) → progress bar + "X of Y (P%)" label
 *     + Upgrade CTA when >90%.
 */

import { type JSX } from 'react';
import { Link } from 'react-router-dom';

import type { FileStorageQuota } from '../../../shared/types/files';
import { useFileStorageQuota } from '../hooks/useFiles';
import {
  QUOTA_UPGRADE_CTA_THRESHOLD_PERCENT,
  formatBytes,
  severityForQuota,
} from '../utils/quotaFormatting';
import './FileQuotaMeter.css';

export interface FileQuotaMeterProps {
  /** Optional className escape hatch for layout. */
  className?: string;
  /** Override quota (used by tests / Storybook); when omitted the hook fetches. */
  quotaOverride?: FileStorageQuota;
  /** Disable the live fetch (used when the page already has the data). */
  disableFetch?: boolean;
}

export function FileQuotaMeter({
  className,
  quotaOverride,
  disableFetch: _disableFetch,
}: FileQuotaMeterProps): JSX.Element | null {
  const { data: fetched, isLoading, error } = useFileStorageQuota();
  const quota = quotaOverride ?? fetched;

  if (isLoading && !quota) {
    return (
      <div
        className={`file-quota-meter file-quota-meter-loading ${className ?? ''}`.trim()}
        data-testid="file-quota-meter-loading"
        aria-busy="true"
      >
        <span className="file-quota-meter-skeleton" aria-hidden="true" />
      </div>
    );
  }

  // Silent on error — degrades gracefully rather than hiding the
  // page behind a fatal banner. The hint surface CAN miss without
  // breaking the user's workflow.
  if (error || !quota) return null;

  if (quota.unlimited) {
    return (
      <section
        className={`file-quota-meter file-quota-meter-unlimited ${className ?? ''}`.trim()}
        data-testid="file-quota-meter"
        data-severity="normal"
        data-unlimited="true"
        role="status"
        aria-label="Storage usage"
      >
        <span className="file-quota-meter-label">
          <strong>Storage:</strong> {formatBytes(quota.used_bytes)} used
          <span className="file-quota-meter-plan-suffix">
            {' '}(unlimited plan)
          </span>
        </span>
      </section>
    );
  }

  // Capped plan — the common case.
  const limit = quota.limit_bytes ?? 0;
  const percentage = quota.percentage ?? 0;
  const severity = severityForQuota(percentage);
  const showUpgradeCta = percentage > QUOTA_UPGRADE_CTA_THRESHOLD_PERCENT;

  return (
    <section
      className={`file-quota-meter file-quota-meter-${severity} ${className ?? ''}`.trim()}
      data-testid="file-quota-meter"
      data-severity={severity}
      role={severity === 'danger' ? 'alert' : 'status'}
      aria-label="Storage usage"
    >
      <div className="file-quota-meter-header">
        <span className="file-quota-meter-label">
          <strong>Storage:</strong> {formatBytes(quota.used_bytes)} of{' '}
          {formatBytes(limit)}
          <span className="file-quota-meter-percent" data-testid="file-quota-meter-percent">
            {' '}({percentage.toFixed(1)}%)
          </span>
        </span>
        {showUpgradeCta && (
          <Link
            to="/settings/subscription"
            className="file-quota-meter-upgrade-cta"
            data-testid="file-quota-meter-upgrade-cta"
          >
            Upgrade for more →
          </Link>
        )}
      </div>
      <div
        className="file-quota-meter-bar"
        role="progressbar"
        aria-valuenow={Math.round(percentage)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuetext={`${percentage.toFixed(1)} percent of plan storage used`}
      >
        <div
          className="file-quota-meter-fill"
          style={{ width: `${Math.min(100, percentage)}%` }}
          data-testid="file-quota-meter-fill"
        />
      </div>
    </section>
  );
}
