/**
 * Phase 260.3.H.1 — customer-education banner for the file detail
 * surface (R1 audit-pass: GAP-A live-update, GAP-B accurate scan-
 * start anchor, GAP-C in-place help disclosure, GAP-D real CSS
 * tokens).
 *
 * Renders a short, friendly explanation of the malware-scan state
 * with a "What is virus scanning?" disclosure (native
 * ``<details>``/``<summary>``). Three behavioural variants:
 *
 *   1. **In-progress** (PENDING_SCAN, within SLA): ``role="status"``
 *      + ``aria-live="polite"`` so screen readers announce the
 *      progress passively. Copy includes an estimated remaining
 *      time from :func:`estimateScanWait`. The estimate
 *      LIVE-UPDATES on a 1 s tick so the customer doesn't watch a
 *      frozen number.
 *   2. **Overdue** (PENDING_SCAN, past the size-tier SLA): bumps
 *      to ``role="alert"`` with copy that explicitly says the scan
 *      is "taking longer than usual" — keeps customers from
 *      retrying frantically while ops investigates.
 *   3. **Terminal failure** (INFECTED / SCAN_ERROR / SCAN_UNAVAILABLE):
 *      ``role="alert"`` with state-specific copy.
 *
 * CLEAN renders nothing — the file detail already shows the green
 * "Clean" pill and an extra banner is just noise.
 *
 * The banner is purely presentational; the polling that drives
 * ``scanStatus`` transitions lives in the parent (``useFileScanStatus``
 * hook from Phase 260.3.D).
 */

import { useEffect, useState, type JSX } from 'react';

import { useTranslation } from '../../../shared/i18n/useTranslation';
import { FileScanStatus } from '../../../shared/types/files';
import { estimateScanWait } from '../utils/scanWaitEstimate';
import './ScanStatusBanner.css';

/**
 * Stable URL pointing at the customer-education doc kept at
 * ``docs/mvpdocs/concepts/virus-scanning.md``. Retained for cross-
 * referencing in operator runbooks + audit reports — the in-product
 * link uses a native disclosure (no SPA routing dependency, no
 * broken URL on production deploys).
 */
export const SCAN_HELP_LINK_HREF = '/docs/concepts/virus-scanning';

/** Re-render cadence while the banner shows a live remaining-time. */
export const SCAN_BANNER_TICK_INTERVAL_MS = 1000;

export interface ScanStatusBannerProps {
  scanStatus: string;
  /** ``File.size`` in bytes — drives the SLA tier. */
  size: number;
  /**
   * Most recent timestamp that signals "scan started" — typically
   * ``File.updated_at`` while ``scan_status === PENDING_SCAN`` (close
   * to when the scan task was enqueued). Falls back to ``created_at``
   * is acceptable but over-counts elapsed time by the upload
   * duration on large files.
   */
  scanStartedAt: string | null;
  /** Injectable for deterministic tests; defaults to ``Date.now()``. */
  now?: number;
  /**
   * Pass ``true`` to disable the internal live-update tick (used by
   * tests that want to assert a single deterministic render).
   * Production callers leave this unset.
   */
  disableLiveUpdate?: boolean;
  /** Optional className escape hatch for layout (margins, max-width). */
  className?: string;
}

function humanizeRemaining(remainingMs: number): string {
  const seconds = Math.max(0, Math.round(remainingMs / 1000));
  if (seconds <= 0) return 'a few moments';
  if (seconds < 60) return `${seconds} seconds`;
  const minutes = Math.round(seconds / 60);
  if (minutes <= 1) return 'about 1 minute';
  return `about ${minutes} minutes`;
}

function humanizeSla(totalSlaMs: number): string {
  const seconds = Math.round(totalSlaMs / 1000);
  if (seconds < 60) return `${seconds} seconds`;
  const minutes = Math.round(seconds / 60);
  return minutes <= 1 ? '1 minute' : `${minutes} minutes`;
}

/**
 * Native ``<details>`` disclosure carrying the customer-facing
 * explanation. Inline content is the load-bearing accessibility
 * affordance — clicking the summary expands the help inline,
 * with no SPA-routing dependency and no risk of a broken URL.
 */
function HelpDisclosure(): JSX.Element {
  const { t } = useTranslation();
  return (
    <details className="scan-status-banner-help" data-testid="scan-status-banner-help">
      <summary
        className="scan-status-banner-help-summary"
        data-testid="scan-status-banner-help-link"
      >
        {t('files.scanBanner.helpLink', 'What is virus scanning?')}
      </summary>
      <div className="scan-status-banner-help-body">
        <p>
          {t(
            'files.scanBanner.help.intro',
            'Every file you upload is automatically checked for malware before downloads are enabled. The scan runs in our environment (never on your machine) using ClamAV with daily-updated signature databases.'
          )}
        </p>
        <p>
          {t(
            'files.scanBanner.help.whatYouSee',
            'You\'ll see one of five statuses on this page:'
          )}
        </p>
        <ul>
          <li>
            <strong>{t('files.scanBanner.status.pending', 'Pending scan')}</strong> —{' '}
            {t(
              'files.scanBanner.help.pending',
              'the scanner is checking the bytes; downloads are temporarily disabled.'
            )}
          </li>
          <li>
            <strong>{t('files.scanBanner.status.clean', 'Clean')}</strong> —{' '}
            {t(
              'files.scanBanner.help.clean',
              'no malware found; downloads are enabled.'
            )}
          </li>
          <li>
            <strong>{t('files.scanBanner.status.infected', 'Infected')}</strong> —{' '}
            {t(
              'files.scanBanner.help.infected',
              'flagged as malware; downloads are permanently blocked. Contact support if you believe this is a false positive.'
            )}
          </li>
          <li>
            <strong>{t('files.scanBanner.status.scanError', 'Scan error')}</strong> —{' '}
            {t(
              'files.scanBanner.help.scanError',
              'the scanner ran but the result couldn\'t be persisted; try re-uploading the file.'
            )}
          </li>
          <li>
            <strong>{t('files.scanBanner.status.unavailable', 'Scan unavailable')}</strong> —{' '}
            {t(
              'files.scanBanner.help.unavailable',
              'scanner service is temporarily down; the platform retries automatically every few minutes.'
            )}
          </li>
        </ul>
        <p>
          {t(
            'files.scanBanner.help.timing',
            'Typical scan times: small files (< 100 MB) finish within 1 minute; medium files (100 MB – 1 GB) within 3 minutes; large files (1 GB+) within 6 minutes. Your file is safely uploaded and stored regardless — only the download is gated until the scan completes.'
          )}
        </p>
      </div>
    </details>
  );
}

export function ScanStatusBanner({
  scanStatus,
  size,
  scanStartedAt,
  now,
  disableLiveUpdate,
  className,
}: ScanStatusBannerProps): JSX.Element | null {
  const { t } = useTranslation();

  // GAP-A live-update fix: re-render every 1 s while the banner
  // shows a remaining-time so the user doesn't watch a frozen
  // number. The tick is gated on PENDING_SCAN + non-frozen ``now``
  // so terminal-state banners (which never animate) don't burn
  // CPU.
  const [tick, setTick] = useState(0);
  const isPending = scanStatus === FileScanStatus.PENDING_SCAN;
  useEffect(() => {
    if (disableLiveUpdate || !isPending || now !== undefined) return;
    const interval = setInterval(() => {
      setTick((t) => t + 1);
    }, SCAN_BANNER_TICK_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [disableLiveUpdate, isPending, now]);
  void tick; // explicitly read so the linter knows we depend on it

  // CLEAN — short-circuit. The pill already conveys "Clean" and an
  // extra banner is pure UI noise on the happy path.
  if (scanStatus === FileScanStatus.CLEAN) return null;

  if (isPending) {
    const estimate = estimateScanWait({ scanStatus, size, uploadedAt: scanStartedAt, now });
    if (!estimate) return null; // defensive — terminal status snuck through
    if (estimate.overdue) {
      return (
        <section
          className={`scan-status-banner scan-status-banner-overdue ${className ?? ''}`.trim()}
          data-testid="scan-status-banner"
          data-scan-status={scanStatus}
          data-overdue="true"
          role="alert"
          aria-live="polite"
        >
          <strong>
            {t('files.scanBanner.overdue.title', 'Scan is taking longer than usual')}
          </strong>{' '}
          <span>
            {t(
              'files.scanBanner.overdue.body',
              `We expected this file to finish scanning within ${humanizeSla(estimate.totalSlaMs)}, but it's still in progress. Operations is automatically alerted; you can wait or come back later — your file is safely uploaded.`
            )}
          </span>{' '}
          <HelpDisclosure />
        </section>
      );
    }
    return (
      <section
        className={`scan-status-banner scan-status-banner-pending ${className ?? ''}`.trim()}
        data-testid="scan-status-banner"
        data-scan-status={scanStatus}
        role="status"
        aria-live="polite"
      >
        <strong>
          {t('files.scanBanner.pending.title', 'Virus scanning in progress')}
        </strong>{' '}
        <span>
          {t(
            'files.scanBanner.pending.body',
            `We're checking this file for malware before downloads are enabled. Estimated time remaining: ${humanizeRemaining(estimate.remainingMs)} (typical ${humanizeSla(estimate.totalSlaMs)}).`
          )}
        </span>{' '}
        <HelpDisclosure />
      </section>
    );
  }

  if (scanStatus === FileScanStatus.INFECTED) {
    return (
      <section
        className={`scan-status-banner scan-status-banner-infected ${className ?? ''}`.trim()}
        data-testid="scan-status-banner"
        data-scan-status={scanStatus}
        role="alert"
        aria-live="polite"
      >
        <strong>
          {t('files.scanBanner.infected.title', 'Malware detected — download blocked')}
        </strong>{' '}
        <span>
          {t(
            'files.scanBanner.infected.body',
            'This file was flagged as infected by our virus scanner and cannot be downloaded. Please contact support if you believe this is a false positive.'
          )}
        </span>{' '}
        <HelpDisclosure />
      </section>
    );
  }

  if (scanStatus === FileScanStatus.SCAN_ERROR) {
    return (
      <section
        className={`scan-status-banner scan-status-banner-error ${className ?? ''}`.trim()}
        data-testid="scan-status-banner"
        data-scan-status={scanStatus}
        role="alert"
        aria-live="polite"
      >
        <strong>{t('files.scanBanner.error.title', 'Scan error')}</strong>{' '}
        <span>
          {t(
            'files.scanBanner.error.body',
            'This file could not be scanned for malware. Downloads are disabled while operations investigates. Try re-uploading the file or contact support.'
          )}
        </span>{' '}
        <HelpDisclosure />
      </section>
    );
  }

  if (scanStatus === FileScanStatus.SCAN_UNAVAILABLE) {
    return (
      <section
        className={`scan-status-banner scan-status-banner-unavailable ${className ?? ''}`.trim()}
        data-testid="scan-status-banner"
        data-scan-status={scanStatus}
        role="alert"
        aria-live="polite"
      >
        <strong>
          {t('files.scanBanner.unavailable.title', 'Virus scanning temporarily unavailable')}
        </strong>{' '}
        <span>
          {t(
            'files.scanBanner.unavailable.body',
            'Our malware scanner is currently unavailable. Downloads are disabled until the service is restored. Please try again later.'
          )}
        </span>{' '}
        <HelpDisclosure />
      </section>
    );
  }

  // Unknown status — render a neutral banner pointing at the help
  // doc rather than a blank space.
  return (
    <section
      className={`scan-status-banner scan-status-banner-unknown ${className ?? ''}`.trim()}
      data-testid="scan-status-banner"
      data-scan-status={scanStatus}
      role="status"
      aria-live="polite"
    >
      <span>
        {t('files.scanBanner.unknown.body', `Malware scan status: ${scanStatus}.`)}
      </span>{' '}
      <HelpDisclosure />
    </section>
  );
}
