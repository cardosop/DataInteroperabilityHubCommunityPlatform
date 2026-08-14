/**
 * Phase 278.T.2 — UX activation telemetry events.
 *
 * Emits ``CustomEvent``s on ``window`` for Phase 278 interaction points:
 * marketplace recommendations, comparison view, quick preview, saved
 * searches, and the unified approval inbox. Follows the
 * ``listingLineageTelemetry.ts`` convention (fire-and-forget, silent
 * failures, zero third-party SDK dependency).
 *
 * Any analytics adapter (PostHog, Amplitude, custom backend collector)
 * can subscribe via ``window.addEventListener('<event>', ...)`` without
 * individual components hard-coding a specific transport.
 */
export type UxActivationEvent =
  // ── Recommendations (278.H.1) ──────────────────────────────────────────
  | 'meshant.recommendations.impression'
  | 'meshant.recommendations.click'
  | 'meshant.recommendations.feedback'
  // ── Comparison view (278.H.3) ──────────────────────────────────────────
  | 'meshant.comparison.opened'
  | 'meshant.comparison.closed'
  // ── Quick preview (278.H.5) ────────────────────────────────────────────
  | 'meshant.preview.opened'
  | 'meshant.preview.closed'
  // ── Saved searches (278.H.4) ───────────────────────────────────────────
  | 'meshant.saved_search.created'
  | 'meshant.saved_search.applied'
  | 'meshant.saved_search.deleted'
  // ── Approval inbox (278.I.1–4) ─────────────────────────────────────────
  | 'meshant.approval_inbox.item_action'
  | 'meshant.approval_inbox.bulk_action';

// ── Detail types ──────────────────────────────────────────────────────────

export interface RecommendationImpressionDetail {
  section: 'trending' | 'you_might_also_like';
  listing_count: number;
  domain?: string;
}

export interface RecommendationClickDetail {
  listing_id: string;
  section: 'trending' | 'you_might_also_like';
}

export interface RecommendationFeedbackDetail {
  listing_id: string;
  helpful: boolean;
}

export interface ComparisonDetail {
  listing_count: number;
  listing_ids: string[];
}

export interface PreviewDetail {
  listing_id: string;
  /** Wall-clock ms from modal mount to close. Only present on closed. */
  duration_ms?: number;
  /** Whether the preview loaded successfully or errored. */
  result: 'loaded' | 'error' | 'dismissed';
}

export interface SavedSearchDetail {
  search_id?: string;
  search_name?: string;
  has_filters: boolean;
  frequency?: string;
}

export interface ApprovalInboxItemActionDetail {
  item_id: string;
  item_type: 'access_request' | 'dsar' | 'breach' | 'dpia' | 'kyb';
  action: 'approve' | 'reject';
  priority: 'high' | 'medium' | 'low';
}

export interface ApprovalInboxBulkActionDetail {
  item_count: number;
  action: 'approve' | 'reject';
  succeeded: number;
  failed: number;
}

// ── Emit helper ───────────────────────────────────────────────────────────

/**
 * Fire-and-forget telemetry emission.
 *
 * Failures are silent in production — telemetry MUST NOT break the
 * primary render path. In dev mode, a console.debug aids local debugging.
 */
export function emitUxActivationEvent(
  event: UxActivationEvent,
  detail?: Record<string, unknown>,
): void {
  try {
    if (typeof window === 'undefined' || typeof CustomEvent === 'undefined') {
      return;
    }
    window.dispatchEvent(new CustomEvent(event, { detail }));
  } catch (err) {
    if (typeof import.meta !== 'undefined' && import.meta.env?.DEV) {
      console.debug('[ux-activation-telemetry] emit failed', event, err);
    }
  }
}
