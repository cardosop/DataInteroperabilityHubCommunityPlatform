/**
 * Phase 278.H.2 — Trust signals at-a-glance bar for listing cards.
 *
 * Shows: KYC status badge, compliance grade, last-updated, and
 * sample-availability indicator. Compact horizontal layout suitable
 * for card footers.
 */
import './TrustSignalsBar.css';

interface TrustSignalsBarProps {
  kycStatus?: string | null;
  complianceGrade?: 'PASS' | 'WARN' | 'FAIL' | 'UNKNOWN' | null;
  sampleAvailable?: boolean;
  updatedAt?: string;
}

export function TrustSignalsBar({
  kycStatus,
  complianceGrade,
  sampleAvailable,
  updatedAt,
}: TrustSignalsBarProps) {
  return (
    <div className="trust-signals-bar" data-testid="trust-signals-bar">
      {kycStatus && (
        <span
          className={`trust-signal trust-signal-kyc trust-signal-kyc-${kycStatus.toLowerCase()}`}
          title={`KYC: ${kycStatus}`}
          data-testid="trust-signal-kyc"
        >
          {kycStatus === 'VERIFIED' ? '✓ Verified' : kycStatus === 'PENDING_REVIEW' ? '⏳ KYC Pending' : '⚠ Unverified'}
        </span>
      )}

      {complianceGrade && complianceGrade !== 'UNKNOWN' && (
        <span
          className={`trust-signal trust-signal-compliance trust-signal-compliance-${complianceGrade.toLowerCase()}`}
          title={`Compliance: ${complianceGrade}`}
          data-testid="trust-signal-compliance"
        >
          {complianceGrade === 'PASS' ? '✓ Pass' : complianceGrade === 'WARN' ? '⚠ Warn' : '✗ Fail'}
        </span>
      )}

      {sampleAvailable && (
        <span
          className="trust-signal trust-signal-sample"
          title="Sample data available"
          data-testid="trust-signal-sample"
        >
          Sample
        </span>
      )}

      {updatedAt && (
        <span
          className="trust-signal trust-signal-updated"
          title={`Updated ${new Date(updatedAt).toLocaleDateString()}`}
          data-testid="trust-signal-updated"
        >
          {formatRelativeDate(updatedAt)}
        </span>
      )}
    </div>
  );
}

function formatRelativeDate(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 1) return 'Today';
  if (diffDays < 2) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
  return `${Math.floor(diffDays / 365)}y ago`;
}
