/**
 * Phase 260.2.C — ScanStatusPill renders all FileScanStatus labels (Vitest + RTL).
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FileScanStatus } from '../../../shared/types/files';
import { ScanStatusPill } from './ScanStatusPill';

describe('ScanStatusPill', () => {
  it.each([
    [FileScanStatus.PENDING_SCAN, 'Pending scan'],
    [FileScanStatus.CLEAN, 'Clean'],
    [FileScanStatus.INFECTED, 'Infected'],
    [FileScanStatus.SCAN_UNAVAILABLE, 'Scan unavailable'],
    [FileScanStatus.SCAN_ERROR, 'Scan error'],
  ])('renders label for %s', (status, label) => {
    render(<ScanStatusPill status={status} />);
    const pill = screen.getByTestId('scan-status-pill');
    expect(pill).toHaveTextContent(label);
    expect(pill).toHaveAttribute('data-scan-status', status);
  });

  it('sets title when scannedAt provided', () => {
    render(
      <ScanStatusPill status={FileScanStatus.CLEAN} scannedAt="2024-06-01T12:00:00.000Z" />
    );
    const pill = screen.getByTestId('scan-status-pill');
    expect(pill.getAttribute('title') ?? '').toMatch(/last scan/i);
  });

  it('uses custom testId for table rows', () => {
    render(<ScanStatusPill status={FileScanStatus.CLEAN} testId="file-scan-abc" />);
    expect(screen.getByTestId('file-scan-abc')).toBeInTheDocument();
    expect(screen.queryByTestId('scan-status-pill')).not.toBeInTheDocument();
  });
});
