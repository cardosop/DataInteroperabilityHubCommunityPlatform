/**
 * Phase 270.B.1.4 — inline banner shown on the marketplace
 * Listing detail page when the linked Contract's marketplace
 * policy has drifted from the snapshot stored on the listing.
 *
 * Modeled on the Phase 250 ``SchemaDriftBanner`` (asset-side
 * schema drift) — same accessibility patterns, same look-and-
 * feel — but adapted for the policy-drift payload shape
 * (``{key: {old, new}}``) which is fundamentally different from
 * schema drift's column-level type-mismatch shape.
 *
 * The component is **purely presentational** — no fetching, no
 * network side-effects. It renders the ``contract_drift_diff``
 * payload returned by the backend on ``GET /marketplace/listings/{id}``
 * and surfaces:
 *
 * 1. A warn-tier heading (this is always non-blocking — the
 *    drifted policy is still STORED on the listing; nothing has
 *    failed, the operator just needs to acknowledge).
 * 2. UX-writer copy explaining what to do next: "Re-publish to
 *    refresh terms."
 * 3. A collapsible per-key table — one row per drifted policy
 *    field, with the snapshotted value vs the current value.
 *
 * Accessibility (WCAG 2.1 AA):
 *
 * - Top-level wrapper is ``<section role="alert"
 *   aria-live="polite">`` so screen readers announce drift on
 *   first render.
 * - Severity is conveyed via colour AND text + icon — not colour
 *   alone (per 1.4.1 Use of Color).
 * - Collapsible section uses native ``<details>`` / ``<summary>``
 *   so keyboard navigation, focus management, and screen-reader
 *   announcements are inherited from the browser (no custom
 *   accordion to test).
 * - The diff table has ``<th scope="col">`` + a ``<caption>`` per
 *   1.3.1 Info and Relationships.
 *
 * Returning null when the listing has no recorded drift keeps
 * the detail page tidy for the overwhelmingly common case.
 */
import type { JSX } from 'react';

import type { ContractDriftDiff } from '../../../shared/types/marketplace';

export interface ContractDriftBannerProps {
  /** Server-emitted drift diff (``listing.contract_drift_diff``). */
  drift: ContractDriftDiff | null | undefined;
  /** ISO-8601 timestamp the drift was first detected. */
  detectedAt?: string | null;
  /** Optional className escape hatch for layout. */
  className?: string;
}

/**
 * Render-safe string representation of a single drift value.
 * Backend values can be primitives, lists, or null — we stringify
 * non-trivial shapes via JSON.stringify so the banner is shape-
 * tolerant.
 */
function renderValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '—';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value);
}

/**
 * Renders nothing when there's no drift to report:
 * - drift is null/undefined (in sync, the common case)
 * - drift is an empty object (in sync; defence in depth)
 */
export function ContractDriftBanner({
  drift,
  detectedAt,
  className,
}: ContractDriftBannerProps): JSX.Element | null {
  if (!drift || Object.keys(drift).length === 0) {
    return null;
  }

  const driftedKeys = Object.keys(drift);

  return (
    <section
      role="alert"
      aria-live="polite"
      aria-label="Contract drift detected"
      data-testid="contract-drift-banner"
      data-severity="WARN"
      className={[
        'rounded-md border p-4 my-4 text-sm',
        'border-amber-300 bg-amber-50 text-amber-900',
        className ?? '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <header className="flex items-baseline gap-2 mb-2">
        <span aria-hidden="true" className="text-lg leading-none">
          ⓘ
        </span>
        <h3 className="font-semibold text-base">
          Contract terms have changed since this listing was published
        </h3>
      </header>

      <p className="mb-3">
        The data contract behind this listing has been updated. The
        listing currently shows the older terms. Re-publish the listing
        to refresh the displayed license, intended/restricted use, and
        pricing to match the contract&apos;s current policy.
      </p>

      {detectedAt && (
        <p className="text-xs mb-3 opacity-90">
          Drift first detected:{' '}
          <time dateTime={detectedAt}>
            {new Date(detectedAt).toLocaleString()}
          </time>
        </p>
      )}

      <details className="mb-2" open={driftedKeys.length <= 5}>
        <summary className="cursor-pointer font-medium">
          Changed fields ({driftedKeys.length})
        </summary>
        <p className="mt-1 mb-2 text-xs opacity-90">
          Each row shows the value stored on the listing (snapshot at
          publish-time) vs. the current contract policy value.
        </p>
        <table className="min-w-full text-xs">
          <caption className="sr-only">Contract drift per-key diff</caption>
          <thead>
            <tr>
              <th scope="col" className="text-left font-semibold pr-4">
                Field
              </th>
              <th scope="col" className="text-left font-semibold pr-4">
                Listing snapshot
              </th>
              <th scope="col" className="text-left font-semibold">
                Current contract
              </th>
            </tr>
          </thead>
          <tbody>
            {driftedKeys.map((key) => (
              <tr key={key}>
                <td className="font-mono pr-4 align-top">{key}</td>
                <td className="font-mono pr-4 align-top break-all">
                  {renderValue(drift[key]?.old)}
                </td>
                <td className="font-mono align-top break-all">
                  {renderValue(drift[key]?.new)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}
