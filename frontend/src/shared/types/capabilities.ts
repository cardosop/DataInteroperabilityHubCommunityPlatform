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
export type AssetCreationBlockedReason = 'ONBOARDING_INCOMPLETE' | 'DISABLED_BY_OPS' | null;

/**
 * Subset of the runtime capabilities response we care about today.
 * Kept narrow on purpose — adding fields here is a deliberate
 * choice, not an opt-in to every backend-side flag.
 */
export interface RuntimeCapabilitiesSnapshot {
  asset_creation: boolean;
  asset_creation_blocked_reason: AssetCreationBlockedReason;
  datasets?: boolean;
  files?: boolean;
  data_quality?: boolean;
  data_quality_advanced?: boolean;
  compliance_consent?: boolean;
  compliance_ropa?: boolean;
  compliance_dpia?: boolean;
  compliance_retention_enforcer?: boolean;
  compliance_dsar?: boolean;
  compliance_breach?: boolean;
  compliance_processor_agreements?: boolean;
  // openspec add-databricks-control-plane P0 — explicit opt-in (strict),
  // like the other paid surfaces.
  databricks?: boolean;
  // Phase 228 F5 lineage flags — settings-side registries
  // (LINEAGE_CAPABILITY_FLAGS), emitted by /api/v1/capabilities/ but NOT
  // path-derived. Strict === true mirrors the backend flags (test env
  // defaults them ON; prod/staging OFF). The SPA gates read these:
  // lineage.snapshots → LineageTimeTravelControls (228.F5 DoD-G8) and
  // lineage.change_notifications → LineageSubscriptionPanel/Page (228.F3).
  // b6 lineage-time-travel failure: the wire sent lineage.snapshots=true
  // but the coercion dropped it, so the controls never mounted.
  'lineage.snapshots'?: boolean;
  'lineage.change_notifications'?: boolean;
  // UX-v2 gate (278.V.17) — runtime-sourced from Tenant.ux_v2_enabled;
  // emitted by /api/v1/capabilities/ and coerced in capabilitiesService.
  ux_v2?: boolean;
  // plan_compliance_pro_pack deliberately NOT here: its source is the /me
  // subscription-plan payload (shared/types/tenants.ts), not the runtime
  // capabilities wire — see the backend wire-contract pin.
}
