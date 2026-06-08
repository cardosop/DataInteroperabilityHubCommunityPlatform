/**
 * Phase 231.5.9 — single source for detail-page axe routes (see _guards.spec.ts parity test).
 * Consumed by `e2e/a11y/axe-detail-pages.spec.ts`.
 */
export const DETAIL_PAGES_AXE_MANIFEST: ReadonlyArray<{ path: string; label: string; mustReachShell?: boolean }> = [
  { path: '/contracts', label: 'contracts-list' },
  {
    path: '/contracts/00000000-0000-0000-0000-000000000000',
    label: 'contracts-detail-not-found',
  },
  { path: '/assets/00000000-0000-0000-0000-000000000000', label: 'assets-detail-not-found' },
  { path: '/datasets', label: 'datasets-list' },
  {
    path: '/datasets/00000000-0000-0000-0000-000000000000',
    label: 'datasets-detail-not-found',
  },
  { path: '/marketplace', label: 'marketplace-list-detail-context' },
  {
    path: '/marketplace/listings/00000000-0000-0000-0000-000000000000',
    label: 'marketplace-listing-not-found',
  },
  { path: '/governance', label: 'governance' },
  { path: '/integrations', label: 'integrations' },
  { path: '/lineage', label: 'lineage' },
  { path: '/observability', label: 'observability' },
  { path: '/audit', label: 'audit-events' },
  { path: '/notifications', label: 'notifications' },
  { path: '/jobs', label: 'jobs' },
  { path: '/webhooks', label: 'webhooks' },
  { path: '/search', label: 'search' },
  {
    path: '/compliance/runs/00000000-0000-0000-0000-000000000000',
    label: 'compliance-run-detail-not-found',
  },
  // Phase 278.Z.1 — new Phase 278 routes added to axe audit manifest
  { path: '/marketplace/saved-searches', label: 'saved-searches-management' },
  { path: '/governance/my-approvals', label: 'my-approvals-inbox' },
  // 284.A.7 — FederatedImportPage a11y + dark mode
  { path: '/federated-import', label: 'federated-import-page' },
  // 284.D.4 — Semantic search facets on catalogue/search page
  { path: '/search', label: 'search-page-semantic-facets' },
  // 283.6.5 — allow_intake_on_compliance_degraded + asset_auto_activate_on_gate_pass routes
  // allow_intake_on_compliance_degraded: compliance run list shows degraded banner when circuit open
  { path: '/compliance', label: 'compliance-run-list' },
  // asset_auto_activate_on_gate_pass: asset creation flow shows auto-activate status
  { path: '/assets/create', label: 'asset-create-flow' },
];
