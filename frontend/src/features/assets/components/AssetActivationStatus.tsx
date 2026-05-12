/**
 * Phase 274.2.4 — AssetActivationStatus
 *
 * Three-state polling for compliance-aware asset activation.
 * Renders a status pill with auto-poll every 30s while scan is pending.
 */
import { useEffect, useState } from 'react';
import { Button } from '../../../shared/components/Button';
import './AssetActivationStatus.css';

interface Props {
  /** One of: COMPLIANCE_SCAN_PENDING, COMPLIANCE_SCAN_FAILED,
   *  COMPLIANCE_NOT_ALLOWED_TO_STORE, COMPLIANCE_THRESHOLD_EXCEEDED, or null */
  blockerCode: string | null;
  details: Record<string, unknown> | null;
  onRetry: () => void;
  isPolling: boolean;
}

const STATE_LABELS: Record<string, string> = {
  COMPLIANCE_SCAN_PENDING: 'Compliance scan pending…',
  COMPLIANCE_SCAN_FAILED: 'Compliance scan failed',
  COMPLIANCE_NOT_ALLOWED_TO_STORE: 'Storage not allowed',
  COMPLIANCE_THRESHOLD_EXCEEDED: 'Compliance risk too high',
};

const STATE_VARIANTS: Record<string, 'info' | 'warning' | 'danger'> = {
  COMPLIANCE_SCAN_PENDING: 'info',
  COMPLIANCE_SCAN_FAILED: 'warning',
  COMPLIANCE_NOT_ALLOWED_TO_STORE: 'danger',
  COMPLIANCE_THRESHOLD_EXCEEDED: 'danger',
};

export function AssetActivationStatus({
  blockerCode,
  details,
  onRetry,
  isPolling,
}: Props) {
  const [retryAfter, setRetryAfter] = useState<number | null>(null);

  // Auto-poll every 30s while scan is pending.
  useEffect(() => {
    if (blockerCode !== 'COMPLIANCE_SCAN_PENDING') return;
    if (details?.retry_after_seconds) {
      setRetryAfter(Number(details.retry_after_seconds));
    }

    const interval = setInterval(() => {
      if (!isPolling) onRetry();
    }, 30_000);
    return () => clearInterval(interval);
  }, [blockerCode, isPolling, onRetry, details]);

  if (!blockerCode) return null;

  const label = STATE_LABELS[blockerCode] || blockerCode;
  const variant = STATE_VARIANTS[blockerCode] || 'info';

  return (
    <div className={`asset-activation-status activation-${variant}`} data-testid="activation-status">
      <span className="activation-pill">
        {label}
      </span>
      {details?.message && (
        <p className="activation-message">{String(details.message)}</p>
      )}
      {retryAfter && (
        <p className="activation-retry-hint">
          Auto-retrying in {retryAfter} seconds…
        </p>
      )}
      {blockerCode !== 'COMPLIANCE_SCAN_PENDING' && (
        <Button variant="secondary" onClick={onRetry} loading={isPolling}>
          Retry
        </Button>
      )}
    </div>
  );
}
