/**
 * ScanStatusBanner tests — Phase 260.3.H.1 + R1 audit-pass.
 *
 * Behavioural tests for the customer-education banner shown on the
 * file detail surface. Real React render via ``@testing-library/react``;
 * no mocks of i18n (we use the real ``useTranslation`` with fallback
 * strings) or of the SLA helper (real ``estimateScanWait``).
 *
 * Engineering invariants under test:
 *   - Renders nothing for terminal CLEAN status (no banner noise on
 *     the happy path).
 *   - Renders for PENDING_SCAN with the estimated wait + help
 *     disclosure + ``role="status"`` + ``aria-live="polite"``.
 *   - LIVE-UPDATES the estimate on a 1 s tick (R1 audit-pass GAP-A).
 *   - Switches to "taking longer than usual" copy + ``role="alert"``
 *     when the SLA is exceeded.
 *   - Renders for INFECTED / SCAN_ERROR / SCAN_UNAVAILABLE terminal-
 *     failure states with appropriate copy and the help disclosure.
 *   - Help disclosure is a native ``<details>``/``<summary>`` with
 *     inline content (R1 audit-pass GAP-C: no broken /docs URL).
 *   - SLA-tier copy reflects the file size: small / medium / large
 *     each yield a different "about N seconds" hint.
 */

import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FileScanStatus } from '../../../shared/types/files';
import {
  SCAN_BANNER_TICK_INTERVAL_MS,
  SCAN_HELP_LINK_HREF,
  ScanStatusBanner,
  type ScanStatusBannerProps,
} from './ScanStatusBanner';
import {
  SCAN_SLA_LARGE_FILE_BYTES,
  SCAN_SLA_LARGE_MS,
  SCAN_SLA_MEDIUM_FILE_BYTES,
  SCAN_SLA_MEDIUM_MS,
  SCAN_SLA_SMALL_MS,
} from '../utils/scanWaitEstimate';

const NOW = Date.parse('2026-05-06T12:00:00Z');

function defaultProps(overrides: Partial<ScanStatusBannerProps> = {}): ScanStatusBannerProps {
  return {
    scanStatus: FileScanStatus.PENDING_SCAN,
    size: 1024,
    scanStartedAt: new Date(NOW - 2_000).toISOString(),
    now: NOW,
    ...overrides,
  };
}

describe('ScanStatusBanner — silent on the happy path', () => {
  it('renders nothing when the scan is CLEAN', () => {
    const { container } = render(
      <ScanStatusBanner {...defaultProps({ scanStatus: FileScanStatus.CLEAN })} />
    );
    expect(container.firstChild).toBeNull();
  });
});

describe('ScanStatusBanner — PENDING_SCAN', () => {
  it('renders the in-progress banner with status role + polite aria-live', () => {
    render(<ScanStatusBanner {...defaultProps()} />);
    const banner = screen.getByTestId('scan-status-banner');
    expect(banner).toHaveAttribute('role', 'status');
    expect(banner).toHaveAttribute('aria-live', 'polite');
    expect(banner).toHaveTextContent(/scanning|in progress|virus/i);
  });

  it('shows an estimated remaining time on the small-file SLA', () => {
    render(<ScanStatusBanner {...defaultProps({ size: 1024 })} />);
    const banner = screen.getByTestId('scan-status-banner');
    // Small SLA = 60s; we passed scanStartedAt 2s ago → ~58s remaining.
    expect(banner.textContent).toMatch(/\b\d+\s*(s|sec|second|minute)/i);
  });

  it('renders different SLA copy for medium-tier files', () => {
    const { container: small } = render(
      <ScanStatusBanner
        {...defaultProps({ size: 1024, scanStartedAt: new Date(NOW).toISOString() })}
      />
    );
    const { container: medium } = render(
      <ScanStatusBanner
        {...defaultProps({
          size: SCAN_SLA_MEDIUM_FILE_BYTES,
          scanStartedAt: new Date(NOW).toISOString(),
        })}
      />
    );
    expect(small.textContent).not.toEqual(medium.textContent);
    expect(medium.textContent).toMatch(/3\s*minute|180\s*sec/i);
  });

  it('renders different SLA copy for large-tier files', () => {
    const { container: large } = render(
      <ScanStatusBanner
        {...defaultProps({
          size: SCAN_SLA_LARGE_FILE_BYTES,
          scanStartedAt: new Date(NOW).toISOString(),
        })}
      />
    );
    expect(large.textContent).toMatch(/6\s*minute|360\s*sec/i);
    void SCAN_SLA_SMALL_MS;
    void SCAN_SLA_MEDIUM_MS;
    void SCAN_SLA_LARGE_MS;
  });

  it('switches to alert role + "taking longer than usual" when overdue', () => {
    render(
      <ScanStatusBanner
        {...defaultProps({
          scanStartedAt: new Date(NOW - SCAN_SLA_SMALL_MS - 30_000).toISOString(),
        })}
      />
    );
    const banner = screen.getByTestId('scan-status-banner');
    expect(banner).toHaveAttribute('role', 'alert');
    expect(banner.textContent).toMatch(/longer than usual|delayed|still scanning/i);
  });
});

describe('ScanStatusBanner — terminal failure states', () => {
  it.each([
    [FileScanStatus.INFECTED, /infected|malware|blocked/i],
    [FileScanStatus.SCAN_ERROR, /error|could not be scanned|failed/i],
    [FileScanStatus.SCAN_UNAVAILABLE, /unavailable|temporarily/i],
  ])('renders alert-role copy for %s', (status, expectedPattern) => {
    render(<ScanStatusBanner {...defaultProps({ scanStatus: status })} />);
    const banner = screen.getByTestId('scan-status-banner');
    expect(banner).toHaveAttribute('role', 'alert');
    expect(banner.textContent).toMatch(expectedPattern);
  });
});

describe('ScanStatusBanner — help disclosure (R1 audit-pass GAP-C)', () => {
  it('renders a native <details>/<summary> disclosure carrying inline help content', () => {
    render(<ScanStatusBanner {...defaultProps()} />);
    const help = screen.getByTestId('scan-status-banner-help');
    expect(help).toBeInTheDocument();
    expect(help.tagName.toLowerCase()).toBe('details');
    const summary = screen.getByTestId('scan-status-banner-help-link');
    expect(summary.tagName.toLowerCase()).toBe('summary');
    expect(summary).toHaveTextContent(/what is virus scanning/i);
  });

  it('renders inline help content describing all 5 scan statuses (zero external URL dependency)', () => {
    render(<ScanStatusBanner {...defaultProps()} />);
    const help = screen.getByTestId('scan-status-banner-help');
    // The disclosure body lists all 5 statuses inline so the
    // explanation works even if the doc site is offline.
    expect(within(help).getByText(/Pending scan/i)).toBeInTheDocument();
    expect(within(help).getByText(/^Clean$/i)).toBeInTheDocument();
    expect(within(help).getByText(/^Infected$/i)).toBeInTheDocument();
    expect(within(help).getByText(/^Scan error$/i)).toBeInTheDocument();
    expect(within(help).getByText(/^Scan unavailable$/i)).toBeInTheDocument();
  });

  it('expands the disclosure on summary click (native browser semantics)', async () => {
    const user = userEvent.setup();
    render(<ScanStatusBanner {...defaultProps()} />);
    const help = screen.getByTestId('scan-status-banner-help') as HTMLDetailsElement;
    expect(help.open).toBe(false);
    await user.click(screen.getByTestId('scan-status-banner-help-link'));
    expect(help.open).toBe(true);
  });

  it('exposes the help disclosure in every variant (terminal + pending + overdue)', () => {
    const states = [
      FileScanStatus.PENDING_SCAN,
      FileScanStatus.INFECTED,
      FileScanStatus.SCAN_ERROR,
      FileScanStatus.SCAN_UNAVAILABLE,
    ];
    for (const status of states) {
      const { unmount } = render(<ScanStatusBanner {...defaultProps({ scanStatus: status })} />);
      expect(screen.getByTestId('scan-status-banner-help')).toBeInTheDocument();
      expect(screen.getByTestId('scan-status-banner-help-link')).toBeInTheDocument();
      unmount();
    }
  });

  it('exports SCAN_HELP_LINK_HREF for cross-referencing in operator runbooks', () => {
    // Stable URL pinned for documentation cross-links; not used as
    // an in-product href (in-product help is the disclosure above).
    expect(SCAN_HELP_LINK_HREF).toBe('/docs/concepts/virus-scanning');
  });
});

describe('ScanStatusBanner — live-update tick (R1 audit-pass GAP-A)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('exports the tick interval for callers + tests', () => {
    expect(SCAN_BANNER_TICK_INTERVAL_MS).toBe(1000);
  });

  it('re-renders the remaining-time estimate when ``now`` is unbound (production path)', () => {
    const baseTime = Date.parse('2026-05-06T12:00:00Z');
    vi.setSystemTime(baseTime);
    render(
      <ScanStatusBanner
        scanStatus={FileScanStatus.PENDING_SCAN}
        size={1024}
        scanStartedAt={new Date(baseTime - 1000).toISOString()}
      />
    );
    const banner = screen.getByTestId('scan-status-banner');
    const initialText = banner.textContent ?? '';
    expect(initialText).toMatch(/\d+\s*seconds/i);

    // Advance system time + fire the interval — the banner MUST
    // re-render with a smaller remaining-time. Without the GAP-A
    // fix the estimate would freeze.
    vi.setSystemTime(baseTime + 5_000);
    act(() => {
      vi.advanceTimersByTime(SCAN_BANNER_TICK_INTERVAL_MS);
    });
    const tickedText = banner.textContent ?? '';
    expect(tickedText).not.toEqual(initialText);
  });

  it('does NOT install an interval for terminal-state banners (CPU hygiene)', () => {
    const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');
    render(<ScanStatusBanner {...defaultProps({ scanStatus: FileScanStatus.INFECTED })} />);
    // Terminal banners never animate; no interval should be armed.
    expect(setIntervalSpy).not.toHaveBeenCalled();
    setIntervalSpy.mockRestore();
  });

  it('does NOT install an interval when ``now`` is bound (deterministic test path)', () => {
    const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');
    render(<ScanStatusBanner {...defaultProps()} />);
    expect(setIntervalSpy).not.toHaveBeenCalled();
    setIntervalSpy.mockRestore();
  });

  it('clears the interval on unmount', () => {
    vi.setSystemTime(NOW);
    const { unmount } = render(
      <ScanStatusBanner
        scanStatus={FileScanStatus.PENDING_SCAN}
        size={1024}
        scanStartedAt={new Date(NOW - 1000).toISOString()}
      />
    );
    const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');
    unmount();
    expect(clearIntervalSpy).toHaveBeenCalled();
    clearIntervalSpy.mockRestore();
  });
});
