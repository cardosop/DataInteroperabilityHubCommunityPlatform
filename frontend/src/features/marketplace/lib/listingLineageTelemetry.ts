/**
 * Phase 228.F1.29 — Frontend telemetry events for the listing
 * lineage panel.
 *
 * Emits `CustomEvent`s on `window` so any analytics adapter
 * (PostHog, Amplitude, custom backend collector) can subscribe via
 * `window.addEventListener('lineage.listing.<event>', ...)` without
 * the panel hard-coding a specific transport.  This keeps the
 * F1.30 bundle-budget happy (≤30 KB gzipped delta) — a backend
 * collector adapter would weigh ~50 KB on its own.
 *
 * Failures are silent — telemetry MUST NOT break the panel's
 * primary render path (mirrors the schema-editor metrics
 * convention from Phase 227 L7.2).
 */

export type LineageListingEvent =
  | 'lineage.listing.opened'        // Panel mounted
  | 'lineage.listing.cta_clicked'    // Buy CTA clicked (summary tier)
  | 'lineage.listing.full_loaded'    // First successful full-tier load
  | 'lineage.listing.error'          // Fetch error visible to the user
  | 'lineage.listing.forbidden';     // 403 ENTITLEMENT_REQUIRED rendered

export interface LineageListingEventDetail {
  listing_id: string;
  detail?: 'summary' | 'full';
  error_code?: string;
  /** Wall-clock ms from panel-mount to event. */
  elapsed_ms?: number;
}

/** Fire-and-forget telemetry emission. */
export function emitLineageListingEvent(
  event: LineageListingEvent,
  detail: LineageListingEventDetail,
): void {
  try {
    if (typeof window === 'undefined' || typeof CustomEvent === 'undefined') {
      return;
    }
    window.dispatchEvent(
      new CustomEvent(event, { detail }),
    );
  } catch (err) {
    if (typeof import.meta !== 'undefined' && import.meta.env?.DEV) {
      // eslint-disable-next-line no-console
      console.debug('[lineage-listing-telemetry] emit failed', err);
    }
  }
}
