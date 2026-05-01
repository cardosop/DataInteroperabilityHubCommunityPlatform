/**
 * Phase 228.F1.17 (REQ-LIN-X-001) — namespaced i18n strings for the
 * cross-tenant marketplace lineage panel.
 *
 * Every customer-visible string in `ListingLineagePanel` is sourced
 * from this module under the `lineage.listing.*` key namespace.  The
 * codebase doesn't yet ship an i18n framework (no react-i18next,
 * no react-intl); this module is the **forward-compatible bridge**:
 * a future translator-layer integration can replace the constant
 * lookups with `t('lineage.listing.cta')` calls without touching
 * the call sites in the panel.
 *
 * Why a constant module not a hook
 * --------------------------------
 * Hook-based i18n drives a re-render on language change.  For F1
 * v1 we accept English-only and re-render is unnecessary; the
 * key-namespacing is what matters for translator readiness.
 */

export const lineageListingStrings = {
  // Tab + heading
  'lineage.listing.tab.label': 'Lineage',
  'lineage.listing.heading': 'Data lineage for this listing',

  // Detail-tier descriptions
  'lineage.listing.summary.description':
    'Pre-purchase lineage preview. Transformation details are hidden until you purchase the listing.',
  'lineage.listing.full.description':
    'Full lineage including transformation references and column-level mappings.',

  // Buy CTA (pre-purchase summary tier)
  'lineage.listing.cta.heading': 'Buy listing to see full lineage',
  'lineage.listing.cta.body':
    'Purchase the listing to unlock the full lineage graph including transformation references, job runs, and column-level mappings.',
  'lineage.listing.cta.button': 'View purchase options',

  // Loading / error states
  'lineage.listing.loading': 'Loading lineage…',
  'lineage.listing.error.title': "We couldn't load the lineage graph",
  'lineage.listing.error.body':
    'The lineage service is unreachable or returned an error. Try again in a moment, and contact support if the problem persists.',
  'lineage.listing.error.retry': 'Retry',

  // Empty state
  'lineage.listing.empty.title': 'No lineage data',
  'lineage.listing.empty.body':
    "This listing's backing asset has no recorded lineage yet. Producers can declare lineage in the contract document or attach upstream references.",

  // Truncation banner (D2 mitigation in F1 STRIDE threat model)
  'lineage.listing.truncated.banner':
    'Lineage graph truncated for performance. Increase max_depth or use the contract Lineage tab for the full graph.',

  // Forbidden-detail rejection
  'lineage.listing.forbidden.title': 'Entitlement required',
  'lineage.listing.forbidden.body':
    'Full lineage is only available to consumers who have purchased this listing.',
} as const;

export type LineageListingStringKey = keyof typeof lineageListingStrings;

/**
 * Lookup helper.  A future i18n integration replaces this body with
 * `t(key)` from react-i18next; today it returns the English fallback.
 */
export function t(key: LineageListingStringKey): string {
  return lineageListingStrings[key];
}
