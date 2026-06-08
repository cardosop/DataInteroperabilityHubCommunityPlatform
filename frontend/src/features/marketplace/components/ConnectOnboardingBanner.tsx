/**
 * ConnectOnboardingBanner — Phase 271.3.6
 *
 * Reusable banner prompting a provider to complete Stripe Connect
 * KYB onboarding. Rendered when a paid-listing publish is blocked
 * with ``code === "connect_kyb_required"`` or when a tenant
 * settings page surfaces an incomplete Connect account.
 *
 * The CTA calls ``/api/v1/billing/connect/onboarding-link/`` which
 * returns a Stripe-hosted onboarding URL. The user completes KYB
 * on Stripe's side, returns to Hub, and can proceed.
 */

import { AlertTriangle } from '../../../shared/config/iconRegistry';
import { debugLogger } from '../../../shared/utils/debugLogger';
import { Button } from '../../../shared/components/Button';
import './ConnectOnboardingBanner.css';

export interface ConnectOnboardingBannerProps {
  /** Human-readable reason the banner is shown (e.g. the ValidationError detail). */
  reason?: string;
  /** URL path for the onboarding-link endpoint. Defaults to the standard API path. */
  onboardingEndpoint?: string;
}

export function ConnectOnboardingBanner({
  reason,
  onboardingEndpoint = '/api/v1/billing/connect/onboarding-link/',
}: ConnectOnboardingBannerProps) {
  const handleStartOnboarding = () => {
    // POST the onboarding-link endpoint to get the Stripe-hosted URL,
    // then redirect the user there.  The endpoint is idempotent —
    // repeat calls for the same tenant reuse the existing Stripe
    // Account and return a fresh AccountLink.
    const token = localStorage.getItem('access_token');
    fetch(onboardingEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : '',
      },
    })
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || 'Failed to start onboarding');
        }
        const data = await res.json();
        if (data.onboarding_url) {
          window.location.href = data.onboarding_url;
        }
      })
      .catch((err) => {
        // eslint-disable-next-line no-console
        debugLogger.error('connect_onboarding_link_failed', { error: String(err) });
      });
  };

  return (
    <div className="connect-onboarding-banner" role="alert">
      <AlertTriangle
        className="connect-onboarding-banner__icon"
        size={20}
        aria-hidden="true"
      />
      <div className="connect-onboarding-banner__content">
        <p className="connect-onboarding-banner__title">
          Stripe Connect onboarding required
        </p>
        {reason && (
          <p className="connect-onboarding-banner__reason">{reason}</p>
        )}
        <p className="connect-onboarding-banner__body">
          To publish paid listings and receive payouts, you must complete
          Stripe&apos;s identity verification (KYB). This takes a few
          minutes and is handled entirely on Stripe&apos;s secure site.
        </p>
      </div>
      <Button
        variant="primary"
        size="md"
        onClick={handleStartOnboarding}
        className="connect-onboarding-banner__cta"
      >
        Start onboarding
      </Button>
    </div>
  );
}
