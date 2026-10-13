/**
 * MVP navigation: hide non-MVP sidebar entries when VITE_MVP_MODE is true.
 * Backend still gates /api/v1/* via MVP_MODE; OpenAPI omits gated paths so
 * capability-based items also disappear after schema load.
 *
 * Track A PR 3: this set is the single source of truth for non-MVP routes
 * across three layers:
 *   1. Sidebar / CommandPalette filter (via isPathHiddenInMvpMode)
 *   2. Frontend route guard (<MvpGatedRoute>, which also calls isPathHiddenInMvpMode)
 *   3. Drift test in mvpGateDrift.test.tsx asserts every NON_MVP_PATHS entry
 *      has a <MvpGatedRoute> wrapper in routes.tsx
 *
 * Convention for adding a new non-MVP feature: see docs/mvp-gate.md.
 */

export const NON_MVP_PATHS: ReadonlySet<string> = new Set([
  '/mesh',
  '/virtualization',
  '/integrations/connections',
  '/communities',
  '/baas',
  '/ml',
  '/transformation',
  '/scheduled-ingestions',
  '/scheduled-exports',
  // Added in Track A PR 3 — close frontend leak parity with the backend
  // MVP_GATED_RELATIVE_PREFIXES additions in PR 1.
  '/developer',
  '/observability',
  // openspec add-databricks-control-plane task 0.15 — mirrors the backend
  // `databricks/` entry in MVP_GATED_RELATIVE_PREFIXES (task 0.13).
  '/databricks',
]);

/**
 * 313.H.4 — deliberate pass-through <MvpGatedRoute> wrappers (Phase
 * 260.3.B datasets/files, Phase 240.4.B.3 dq). The backend MVP gate
 * (hub/apps/api/mvp_mode.py) does NOT include these core prefixes, so
 * the wrapper renders children unchanged. Kept for the CapabilityRoute
 * pairing + future gating; the drift test's inverse rule accepts them
 * via this explicit list so NEW accidental gates stay caught.
 */
export const MVP_GATE_PASS_THROUGH_PATHS: ReadonlySet<string> = new Set([
  '/datasets',
  '/files',
  '/dq',
]);

const MVP_PREFIX_PATHS = ['/ai/'];

export function isPathHiddenInMvpMode(path: string, mvpModeEnabled: boolean): boolean {
  if (!mvpModeEnabled) return false;
  if (NON_MVP_PATHS.has(path)) return true;
  return MVP_PREFIX_PATHS.some((prefix) => path.startsWith(prefix));
}

export function isMvpModeEnabledFromEnv(): boolean {
  return import.meta.env.VITE_MVP_MODE === 'true';
}
