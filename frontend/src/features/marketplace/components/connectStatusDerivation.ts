/**
 * Stripe Connect status derivation (Phase 271.3).
 *
 * Lives in its own module (rather than co-located with
 * ``ConnectStatusBadge``) so Vite's Fast Refresh boundary stays
 * component-only. ``react-refresh/only-export-components`` enforces
 * this — without the split, edits to the badge component invalidate
 * the derivation too and HMR falls back to a full page reload.
 */

export type ConnectStatus = 'verified' | 'pending' | 'restricted' | 'disabled' | 'not_onboarded';

/**
 * Derive the Connect KYB state from the account's Stripe flags.
 *
 * - ``verified`` — charges_enabled AND payouts_enabled (fully onboarded)
 * - ``pending`` — details_submitted but charges_enabled still False (KYB in progress)
 * - ``restricted`` — charges_enabled but NOT payouts_enabled
 * - ``disabled`` — neither enabled (not started, or deauthorized)
 * - ``not_onboarded`` — no ConnectAccount row at all (caller passes nullish props)
 */
export function deriveConnectStatus(
  chargesEnabled?: boolean | null,
  payoutsEnabled?: boolean | null,
  detailsSubmitted?: boolean | null,
): ConnectStatus {
  if (chargesEnabled === null || chargesEnabled === undefined) {
    return 'not_onboarded';
  }
  if (chargesEnabled && payoutsEnabled) {
    return 'verified';
  }
  if (chargesEnabled && !payoutsEnabled) {
    return 'restricted';
  }
  if (detailsSubmitted && !chargesEnabled) {
    return 'pending';
  }
  return 'disabled';
}
