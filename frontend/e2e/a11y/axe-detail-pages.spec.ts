/**
 * Phase 226.F5 — Axe coverage on detail-page surfaces.
 *
 * Third leg of the F5 sprinkle (after axe-critical-pages.spec.ts and
 * axe-interactive-states.spec.ts). This spec rounds out coverage on
 * the detail-page family (per-resource pages where forms, action
 * buttons, and metadata cards live), which is where the visual /
 * interactive surface area is densest and a11y regressions tend to
 * land first.
 *
 * Each test loads a representative detail or list-detail surface and
 * audits via the shared `runAxeAudit` helper. Hard gate on critical /
 * serious; moderate / minor are logged for the team's ratchet.
 *
 * Real backend only — no mocks.
 */

import { expect, test } from '@playwright/test';
import {
  getTenantAdminUser,
  getTestUser,
  loginUser,
  type TestUser,
} from '../fixtures/auth';
import {
  runAxeAudit,
  expectNoSeriousViolations,
  summarizeViolations,
} from '../fixtures/axeAudit';

async function audit(page: import('@playwright/test').Page, label: string) {
  const result = await runAxeAudit(page, label);
  expectNoSeriousViolations(result);
  if (result.totalCount > 0) {
    // intentional: surfaces moderate/minor violations to run output without failing the build — mirrors the convention from the sibling axe-* specs.
    console.warn(summarizeViolations(result));
  }
  return result;
}

interface RouteToAudit {
  path: string;
  label: string;
  mustReachShell?: boolean;
  /**
   * Per-route persona — defaults to the standard test user. Routes
   * behind the /governance role guard (TENANT_ADMIN/DPO/LEGAL_ADMIN/
   * SECURITY_ADMIN/PLATFORM_ADMIN) MUST name the admitted persona:
   * auditing the /403 page the default DATA_PROVIDER lands on is dead
   * coverage in the same class as the removed /lineage 404 entry.
   */
  user?: () => Promise<TestUser>;
  /**
   * Route-specific content to wait for before the audit — without it,
   * the shell-ready wait can resolve while the surface is still a
   * skeleton/loading state and the audit scans a transient frame.
   */
  contentSelector?: string;
}

const ROUTES_TO_AUDIT: RouteToAudit[] = [
  { path: '/contracts', label: 'contracts-list' },
  // Phase 230.5.8 (REQ-SEM-RELATIONSHIPS-001) — contract-detail
  // surface that hosts the new RelationshipsPanel + RDF triples
  // table.  ``/contracts/00000000-0000-0000-0000-000000000000``
  // is a deterministic-but-non-existent UUID that exercises the
  // detail-page error/not-found shell — captures axe violations
  // on the rendered surface even when the test tenant has no
  // seeded contracts.  Phase 230.5.MetaDoD audit fix M2: prior
  // entry ``/contracts/0`` was rejected by the React Router UUID
  // matcher and never rendered any contract surface — replaced
  // with a real-shape UUID that does exercise the detail page's
  // error / not-found state.  RelationshipsPanel itself is
  // covered by the dedicated unit-test file (M3+M4+M5).
  { path: '/contracts/00000000-0000-0000-0000-000000000000', label: 'contracts-detail-not-found' },
  { path: '/datasets', label: 'datasets-list' },
  { path: '/marketplace', label: 'marketplace-list-detail-context' },
  { path: '/governance', label: 'governance' },
  // close-test-coverage-gaps 5.2 — the unified approval inbox (278.I.1).
  // TENANT_ADMIN persona: the parent /governance guard admits it, so the
  // audit scans the REAL inbox (the 2.4 contrast fixes live here), not a
  // /403 page.
  {
    path: '/governance/my-approvals',
    label: 'governance-my-approvals-inbox',
    user: getTenantAdminUser,
    contentSelector:
      '[data-testid="my-approvals-inbox"], .my-approvals-inbox, .my-approvals-inbox__empty, .error-display, [data-testid="error-display"]',
  },
  { path: '/integrations', label: 'integrations' },
  { path: '/observability', label: 'observability' },
  { path: '/audit', label: 'audit-events' },
  { path: '/notifications', label: 'notifications' },
  { path: '/jobs', label: 'jobs' },
  { path: '/webhooks', label: 'webhooks' },
  { path: '/search', label: 'search' },
  // close-test-coverage-gaps 5.2 — the public pricing surface
  // (285.13.11.2, shipped under 3.1). Public route: the audit runs with
  // the default authenticated user; the page renders for anonymous
  // visitors too.
  {
    path: '/pricing',
    label: 'pricing',
    contentSelector:
      '.pricing-page, [data-testid="pricing-page"], .error-display, [data-testid="error-display"], h1',
  },

  // ═══ close-test-coverage-gaps 5.4 — previously unaudited surfaces ═══
  // (self-service settings, mesh, virtualization, files, social, baas,
  // developer, scheduled ops). "/social" from the task maps to
  // /communities — the /social route is a pure redirect (routes.tsx
  // Navigate → /communities, or /coming-soon under MVP).
  { path: '/settings/profile', label: 'settings-profile', contentSelector: '.profile-page, .error-display, [data-testid="error-display"], h1' },
  { path: '/settings/sessions', label: 'settings-sessions', contentSelector: '.session-list-page, .session-list-table, .session-list-empty, .error-display, [data-testid="error-display"], h1' },
  { path: '/settings/api-keys', label: 'settings-api-keys', contentSelector: '.auth-api-key-list-page, .error-display, [data-testid="error-display"], h1' },
  // Tenant settings behind the TENANT_ADMIN guard — admin persona so the
  // audit scans the real settings surface, not the /403 page.
  {
    path: '/settings/tenant',
    label: 'settings-tenant',
    user: getTenantAdminUser,
    contentSelector: '[data-testid="tenant-settings-page"], .tenant-settings-page, .error-display, [data-testid="error-display"], h1',
  },
  { path: '/mesh', label: 'mesh-list', contentSelector: '.mesh-domain-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1' },
  { path: '/virtualization', label: 'virtualization-list', contentSelector: '.virtual-dataset-list-page, [data-testid="virtual-dataset-list-page"], .virtual-dataset-list-header, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1' },
  { path: '/files', label: 'files-list', contentSelector: '.file-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1' },
  { path: '/communities', label: 'communities', contentSelector: '.communities-page, .communities-tab, .error-display, [data-testid="error-display"], .empty-state, [data-testid="empty-state"], h1' },
  { path: '/baas', label: 'baas', contentSelector: '.baas-page, .error-display, [data-testid="error-display"], .empty-state, [data-testid="empty-state"], h1' },
  { path: '/developer', label: 'developer-portal', contentSelector: '.developer-portal-page, .developer-page, .error-display, [data-testid="error-display"], h1' },
  { path: '/scheduled-ingestions', label: 'scheduled-ingestions-list', contentSelector: '[data-testid="scheduled-ingestion-list-page"], .scheduled-ingestion-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1' },
  { path: '/scheduled-exports', label: 'scheduled-exports-list', contentSelector: '.scheduled-export-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1' },
];

test.describe('A11y axe coverage — detail / list pages @a11y @critical', () => {
  test.setTimeout(120_000);

  for (const route of ROUTES_TO_AUDIT) {
    test(`${route.path} audits clean`, async ({ page }) => {
      const user = route.user ? await route.user() : await getTestUser();
      await loginUser(page, user);
      await page.goto(route.path, { waitUntil: 'domcontentloaded' });
      // Wait for either the app shell OR a known terminal state (capability-gated /
      // unavailable / 404). Either is a valid a11y target.
      await page
        .locator('.app-header, [data-testid="app-header"], .unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"], .not-found-page, .disabled-capability-page, [data-testid="disabled-capability-page"]')
        .first()
        .waitFor({ state: 'visible', timeout: 15_000 })
        .catch(() => {
          // intentional: SPA may render a route-specific empty/loading state without our terminal selectors; the audit below scans whichever state surfaced — that's the a11y target regardless of which path the SPA settled on.
        });
      if (route.contentSelector) {
        await page
          .locator(route.contentSelector)
          .first()
          .waitFor({ state: 'visible', timeout: 30_000 })
          .catch(() => {
            // intentional: the surface may legitimately settle on an
            // error/empty state not covered by the content selector; the
            // audit below still scans the rendered frame.
          });
      }
      if (route.mustReachShell) {
        await expect(page.locator('.app-header, [data-testid="app-header"]').first()).toBeVisible({ timeout: 15_000 });
      }
      await audit(page, route.label);
    });
  }
});
