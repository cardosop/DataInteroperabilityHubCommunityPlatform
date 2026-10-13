/**
 * 313.H.4 — paid-route capability gating (single source of truth).
 *
 * Every route whose feature belongs to a PAID backend app must be wrapped
 * in ``<CapabilityRoute capability={key}>`` so core-only deployments
 * (whose OpenAPI schema omits the paid paths) redirect to /unavailable
 * instead of rendering a broken page against an absent API. This map
 * drives BOTH the wrappers in routes.tsx and the drift test in
 * paidRouteDrift.test.tsx (forward + inverse + nav drift).
 *
 * Key → prefix. A route is "under" a prefix when its full path equals
 * the prefix or starts with `prefix + '/'` (nested children inherit
 * the parent wrapper via the route-tree walk).
 *
 * NOT gated here (deliberately):
 *  - `/settings/cost` — cost tracking is the CORE analytics app
 *    (``/api/v1/analytics/costs/``; its billing-derived fields degrade
 *    in core-only, see hub/apps/api/analytics/cost_tracking.py).
 *  - `/search` — permanently MVP-in-scope, never capability-gated
 *    (Phase 273.1 contract).
 */
export const PAID_ROUTE_CAPABILITIES: Readonly<Record<string, string>> = {
  '/marketplace': 'marketplace',
  '/integrations': 'integrations.marketplace',
  '/settings/subscription': 'billing',
  '/settings/cost-overview': 'billing',
  '/settings/revenue': 'billing.stripe_connect',
  '/admin/connect': 'billing.stripe_connect',
};

/** True when `path` equals the prefix or lives under it. */
export function isPathUnderPaidPrefix(path: string): boolean {
  return Object.keys(PAID_ROUTE_CAPABILITIES).some(
    (prefix) => path === prefix || path.startsWith(`${prefix}/`),
  );
}

/** The capability key a paid path must be gated with, or undefined. */
export function paidCapabilityForPath(path: string): string | undefined {
  for (const [prefix, key] of Object.entries(PAID_ROUTE_CAPABILITIES)) {
    if (path === prefix || path.startsWith(`${prefix}/`)) return key;
  }
  return undefined;
}
