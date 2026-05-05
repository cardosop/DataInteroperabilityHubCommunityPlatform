/**
 * Capabilities Types
 * For runtime capability detection and gating
 */

export interface Capability {
  name: string;
  available: boolean;
  endpoint?: string;
  operationId?: string;
}

export interface CapabilitiesMap {
  [key: string]: Capability;
}

export interface OpenAPISchema {
  paths: Record<string, Record<string, unknown>>;
  components?: {
    schemas?: Record<string, unknown>;
  };
}

/**
 * Phase 250.6.D.2 — discriminator the backend ``GET /api/v1/capabilities/``
 * endpoint returns alongside ``asset_creation``. Lets the SPA branch
 * UX between "incomplete onboarding" (CTA back to onboarding flow)
 * and "ops disabled" (generic disabled page). ``null`` when the
 * gate is open (the normal case).
 */
export type AssetCreationBlockedReason =
  | 'ONBOARDING_INCOMPLETE'
  | 'DISABLED_BY_OPS'
  | null;

/**
 * Subset of the runtime capabilities response we care about today.
 * Kept narrow on purpose — adding fields here is a deliberate
 * choice, not an opt-in to every backend-side flag.
 */
export interface RuntimeCapabilitiesSnapshot {
  asset_creation: boolean;
  asset_creation_blocked_reason: AssetCreationBlockedReason;
}
