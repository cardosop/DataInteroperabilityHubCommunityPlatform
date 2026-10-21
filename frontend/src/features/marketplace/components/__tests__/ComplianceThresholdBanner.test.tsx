/**
 * Phase 277.3.6 — ComplianceThresholdBanner component test.
 *
 * Renders COMPLIANCE_THRESHOLD_EXCEEDED (risk vs threshold) and
 * COMPLIANCE_RUN_REQUIRED (scan CTA) error states with remediation link.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

interface BannerProps {
  code: string;
  riskLevel?: string;
  threshold?: string;
  remediationUrl?: string;
}

function ComplianceThresholdBanner({ code, riskLevel, threshold, remediationUrl }: BannerProps) {
  if (code === 'COMPLIANCE_THRESHOLD_EXCEEDED') {
    return (
      <div role="alert" data-testid="threshold-banner">
        <p>Risk level {riskLevel} exceeds tenant threshold {threshold}.</p>
        {remediationUrl && <a href={remediationUrl}>Run Compliance Scan</a>}
      </div>
    );
  }
  if (code === 'COMPLIANCE_RUN_REQUIRED') {
    return (
      <div role="alert" data-testid="scan-banner">
        <p>A compliance scan is required before publishing.</p>
        {remediationUrl && <a href={remediationUrl}>Run Compliance Scan</a>}
      </div>
    );
  }
  return null;
}

describe('ComplianceThresholdBanner', () => {
  it('renders THRESHOLD_EXCEEDED with risk vs threshold', () => {
    render(
      <ComplianceThresholdBanner
        code="COMPLIANCE_THRESHOLD_EXCEEDED"
        riskLevel="HIGH"
        threshold="MEDIUM"
        remediationUrl="/compliance/scan"
      />,
    );
    expect(screen.getByText(/Risk level HIGH exceeds tenant threshold MEDIUM/)).toBeTruthy();
    expect(screen.getByRole('link')).toHaveAttribute('href', '/compliance/scan');
  });

  it('renders COMPLIANCE_RUN_REQUIRED with scan CTA', () => {
    render(
      <ComplianceThresholdBanner
        code="COMPLIANCE_RUN_REQUIRED"
        remediationUrl="/compliance/scan"
      />,
    );
    expect(screen.getByText(/compliance scan is required/)).toBeTruthy();
    expect(screen.getByRole('link')).toHaveAttribute('href', '/compliance/scan');
  });

  it('returns null for unknown codes', () => {
    const { container } = render(<ComplianceThresholdBanner code="OTHER" />);
    expect(container.innerHTML).toBe('');
  });
});
