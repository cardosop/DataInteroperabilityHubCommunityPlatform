/**
 * ConnectStatusBadge — Phase 271.3 (shared component)
 *
 * Renders a colour-coded pill/badge reflecting the Stripe Connect
 * account's current KYB verification state.  Used across:
 * - ProviderRevenuePage (payout dashboard header)
 * - ListingPublishPage (publish-gate inline status)
 * - TenantSettingsPage (Connect onboarding section)
 *
 * Status derivation:
 * - ``verified`` — charges_enabled AND payouts_enabled (fully onboarded)
 * - ``pending`` — details_submitted but charges_enabled still False (KYB in progress)
 * - ``restricted`` — charges_enabled but NOT payouts_enabled
 * - ``disabled`` — neither enabled (not started, or deauthorized)
 * - ``not_onboarded`` — no ConnectAccount row at all (caller passes nullish props)
 */

import './ConnectStatusBadge.css';
import { deriveConnectStatus, type ConnectStatus } from './connectStatusDerivation';

export interface ConnectStatusBadgeProps {
  chargesEnabled?: boolean | null;
  payoutsEnabled?: boolean | null;
  detailsSubmitted?: boolean | null;
}

const STATUS_CONFIG: Record<ConnectStatus, { label: string; cssClass: string }> = {
  verified:       { label: 'Verified',       cssClass: 'connect-status-badge--verified' },
  pending:        { label: 'Pending',        cssClass: 'connect-status-badge--pending' },
  restricted:     { label: 'Restricted',     cssClass: 'connect-status-badge--restricted' },
  disabled:       { label: 'Disabled',       cssClass: 'connect-status-badge--disabled' },
  not_onboarded:  { label: 'Not onboarded',  cssClass: 'connect-status-badge--not-onboarded' },
};

export function ConnectStatusBadge({
  chargesEnabled,
  payoutsEnabled,
  detailsSubmitted,
}: ConnectStatusBadgeProps) {
  const status = deriveConnectStatus(chargesEnabled, payoutsEnabled, detailsSubmitted);
  const config = STATUS_CONFIG[status];

  return (
    <span
      className={`connect-status-badge ${config.cssClass}`}
      role="status"
      aria-label={`Stripe Connect status: ${config.label}`}
    >
      {config.label}
    </span>
  );
}
