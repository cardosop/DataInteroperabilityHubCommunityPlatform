/**
 * Phase 250.6.A.5 — generic disabled-capability landing page.
 *
 * Used by `<CapabilityRoute>` as the redirect target when a route's
 * required capability is disabled for the current tenant. The
 * component is REUSABLE across capabilities (not hardcoded to
 * asset_creation) so the same surface serves every kill-switched
 * feature in the platform.
 *
 * UX contract:
 *
 * 1. Render a clear "this capability is disabled for your tenant"
 *    explanation, NOT a generic 403. Operator-facing copy explicitly
 *    mentions which capability is off so the user can request the
 *    right thing from their administrator.
 *
 * 2. Surface the capability name (e.g. `asset_creation`) so the
 *    user can quote it verbatim when contacting support — debugging
 *    reasons.
 *
 * 3. Carry a "back to dashboard" CTA so the user has an obvious
 *    next action (NOT a dead-end page).
 *
 * 4. NEVER auto-redirect anywhere — landing here means the user
 *    explicitly tried to reach the disabled feature, and a silent
 *    redirect would mask the problem.
 *
 * The component reads the capability name from React Router's
 * `location.state.capability` (set by `<CapabilityRoute>` on its
 * `<Navigate>` redirect). When state is missing (direct navigation
 * to `/unavailable`), falls back to a generic "feature unavailable"
 * message.
 */
import { Link, useLocation } from 'react-router-dom';

export interface DisabledCapabilityPageProps {
  /**
   * Optional explicit capability name. When unset, reads from
   * `location.state.capability`. Provided for direct rendering
   * outside the `<CapabilityRoute>` redirect path (e.g. tests).
   */
  capability?: string;
}

/** Human-readable copy keyed by capability name. */
const CAPABILITY_COPY: Record<
  string,
  { title: string; explanation: string; adminAction: string }
> = {
  asset_creation: {
    title: 'Asset creation is currently disabled',
    explanation:
      'Your administrator has disabled the ability to create new assets ' +
      'for this tenant. This is a per-tenant setting (not a platform outage).',
    adminAction:
      'Contact your tenant administrator to re-enable asset creation. ' +
      'Reference the capability key "asset_creation" when requesting changes.',
  },
};

const DEFAULT_COPY = {
  title: 'This feature is currently unavailable',
  explanation:
    'The feature you tried to reach is not available for your tenant.',
  adminAction:
    'Contact your tenant administrator to request access to this feature.',
};

export function DisabledCapabilityPage({
  capability: explicitCapability,
}: DisabledCapabilityPageProps = {}) {
  const location = useLocation();
  // location.state may be null (direct nav) or an object set by the
  // <CapabilityRoute> redirect. The `capability` field is set when
  // the route gate fires.
  const stateCapability = (location.state as { capability?: string } | null)
    ?.capability;
  const capability = explicitCapability ?? stateCapability ?? null;
  const copy = capability && CAPABILITY_COPY[capability]
    ? CAPABILITY_COPY[capability]
    : DEFAULT_COPY;

  return (
    <main
      className="disabled-capability-page"
      role="main"
      data-testid="disabled-capability-page"
      data-capability={capability ?? 'unknown'}
    >
      <header>
        <h1>{copy.title}</h1>
      </header>
      <p>{copy.explanation}</p>
      <p>{copy.adminAction}</p>
      {capability && (
        <p className="capability-key">
          <strong>Capability key:</strong>{' '}
          <code data-testid="capability-key">{capability}</code>
        </p>
      )}
      <p>
        <Link to="/" data-testid="back-to-dashboard">
          Back to dashboard
        </Link>
      </p>
    </main>
  );
}
