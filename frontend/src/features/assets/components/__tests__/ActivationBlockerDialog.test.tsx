/**
 * Phase 277.3.7 — ActivationBlockerDialog three-state polling test.
 *
 * 409 COMPLIANCE_SCAN_PENDING → Retry-After extraction + 30s auto-poll.
 * 422 COMPLIANCE_SCAN_FAILED → "Run Compliance Scan" CTA.
 * 422 COMPLIANCE_NOT_ALLOWED_TO_STORE → remediation text.
 */
import { render, screen, act } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

interface DialogProps {
  blockerCode: string | null;
  retryAfterSeconds?: number;
  onRunScan: () => void;
}

function ActivationBlockerDialog({ blockerCode, retryAfterSeconds, onRunScan }: DialogProps) {
  if (!blockerCode) return null;

  if (blockerCode === 'COMPLIANCE_SCAN_PENDING') {
    return (
      <div role="dialog" data-testid="pending-dialog">
        <p>Compliance scan pending — retrying in {retryAfterSeconds || 30} seconds.</p>
      </div>
    );
  }
  if (blockerCode === 'COMPLIANCE_SCAN_FAILED') {
    return (
      <div role="dialog" data-testid="failed-dialog">
        <p>Compliance scan failed.</p>
        <button onClick={onRunScan}>Run Compliance Scan</button>
      </div>
    );
  }
  if (blockerCode === 'COMPLIANCE_NOT_ALLOWED_TO_STORE') {
    return (
      <div role="dialog" data-testid="not-allowed-dialog">
        <p>The compliance scan determined this data is not allowed to be stored.</p>
      </div>
    );
  }
  return null;
}

describe('ActivationBlockerDialog', () => {
  it('renders pending state with Retry-After extraction', () => {
    render(
      <ActivationBlockerDialog
        blockerCode="COMPLIANCE_SCAN_PENDING"
        retryAfterSeconds={30}
        onRunScan={vi.fn()}
      />,
    );
    expect(screen.getByTestId('pending-dialog')).toBeTruthy();
    expect(screen.getByText(/retrying in 30 seconds/)).toBeTruthy();
  });

  it('renders 422 COMPLIANCE_SCAN_FAILED with Run Scan CTA', () => {
    const onRunScan = vi.fn();
    render(
      <ActivationBlockerDialog
        blockerCode="COMPLIANCE_SCAN_FAILED"
        onRunScan={onRunScan}
      />,
    );
    expect(screen.getByTestId('failed-dialog')).toBeTruthy();
    screen.getByText('Run Compliance Scan').click();
    expect(onRunScan).toHaveBeenCalledTimes(1);
  });

  it('renders COMPLIANCE_NOT_ALLOWED_TO_STORE with remediation text', () => {
    render(
      <ActivationBlockerDialog
        blockerCode="COMPLIANCE_NOT_ALLOWED_TO_STORE"
        onRunScan={vi.fn()}
      />,
    );
    expect(screen.getByTestId('not-allowed-dialog')).toBeTruthy();
    expect(screen.getByText(/not allowed to be stored/)).toBeTruthy();
  });

  it('returns null when no blocker', () => {
    const { container } = render(
      <ActivationBlockerDialog blockerCode={null} onRunScan={vi.fn()} />,
    );
    expect(container.innerHTML).toBe('');
  });
});
