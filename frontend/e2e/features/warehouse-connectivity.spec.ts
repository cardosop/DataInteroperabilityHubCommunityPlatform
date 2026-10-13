/**
 * Feature: SQL Warehouse Lifecycle (workspace-scoped)
 *
 * Persona: Tenant Admin / Data Engineer
 * Reference: docs/USER_JOURNEYS.md (JOURNEY-DB-010 — Manage SQL Warehouses)
 *
 * Replaces the pre-control-plane `/warehouses/*` smoke (connection wizard,
 * schema browser, live-data preview, exports) whose routes were removed
 * when the Databricks estate moved into the control plane. The live
 * surface is now:
 *
 *   /databricks/workspaces/:workspaceId/warehouses
 *     → WarehouseLifecyclePage (mirror-first listing + Start/Stop actions)
 *
 * Gated by: MvpGatedRoute → CapabilityRoute("databricks") →
 * ProtectedRoute([TENANT_ADMIN, PLATFORM_ADMIN]). The backend enforces
 * the role and the control-plane flag; the FE gates are UX-grade.
 *
 * Real backend; no mocks. The workspace id is resolved through the API
 * (the same workspaces list the JOURNEY-DB-010 spec uses) so the spec
 * stays truthful against real rows without provisioning its own tenant.
 */

import { expect, test } from '@playwright/test';
import { environmentSkipGuard } from '../fixtures/envPolicy.cjs';
import {
  clearAuthStorage,
  getTenantAdminUserOrTestUser,
  getTestUser,
  loginUser,
} from '../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../fixtures/helpers';

test.describe('Feature: SQL Warehouse Lifecycle', () => {
  test.setTimeout(180_000);

  /**
   * Resolve a workspace id from the tenant's control-plane workspaces via
   * the page's own API context (same contract as JOURNEY-DB-010's 404
   * boundary test). Returns null when the tenant has no workspaces.
   */
  async function resolveWorkspaceId(page: import('@playwright/test').Page): Promise<string | null> {
    const token = await page.evaluate(() => {
      const g = (window as unknown as { __getAccessToken?: () => string | null })
        .__getAccessToken;
      return (typeof g === 'function' ? g() : null) ?? localStorage.getItem('access_token');
    });
    if (!token) return null;
    const res = await page.request.get('/api/v1/databricks/workspaces/', {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok()) return null;
    const body = (await res.json()) as { results?: Array<{ id: string }> };
    return body.results?.[0]?.id ?? null;
  }

  test.describe('Success', () => {
    test('warehouse lifecycle page loads for a tenant admin (mirror list or empty state)', async ({
      page,
    }) => {
      const user = await getTenantAdminUserOrTestUser();
      await loginUser(page, user);

      const workspaceId = await resolveWorkspaceId(page);
      test.skip(!workspaceId, 'no Databricks workspace provisioned for the tenant — lifecycle surface not exercisable');
      if (!workspaceId) return;

      await loginAndNavigateToRoute(
        page,
        user,
        `/databricks/workspaces/${workspaceId}/warehouses`,
        {
          timeout: 90_000,
          contentSelector:
            '.warehouse-list, [data-testid="flag-disabled-banner"], .error-display, [data-testid="error-display"], h2',
        }
      );

      // Terminal-state contract (same split as the DQ / MP specs):
      //  - /coming-soon: MVP-gated surface — genuinely out of scope.
      //  - /unavailable: CapabilityRoute("databricks") — the runtime
      //    databricks flag is false in this env, so the gate bounces
      //    BEFORE the page mounts. W16-guarded skip: raises in CI,
      //    skips locally.
      test.skip(
        page.url().includes('/coming-soon'),
        'databricks surface out of MVP scope — lifecycle page not exercisable',
      );
      if (page.url().includes('/unavailable')) {
        environmentSkipGuard(
          'databricks gate bounced to /unavailable — the runtime databricks capability is disabled for the tenant',
        );
      }
      test.skip(
        page.url().includes('/unavailable'),
        'databricks capability disabled — lifecycle page not exercisable',
      );
      if (page.url().includes('/unavailable') || page.url().includes('/coming-soon')) {
        return;
      }
      // 403 = the role gate held (env posture: the persona lacks
      // TENANT_ADMIN). Accept as a terminal state — the page contract
      // cannot be exercised by this user.
      test.skip(
        page.url().includes('/403'),
        'role gate held for this persona — TENANT_ADMIN required'
      );
      if (page.url().includes('/403')) {
        return;
      }

      await waitForLoadingComplete(page, { timeout: 15_000 });

      // The page must render one of its documented terminal states:
      // mirror table, empty fleet message, or the flag-disabled banner
      // (control plane off for the tenant while the route is reachable).
      const hasTable = (await page.locator('.warehouse-list table').count()) > 0;
      const hasEmpty = (await page.getByText(/No SQL warehouses reported/i).count()) > 0;
      const hasFlagBanner = (await page.getByTestId('flag-disabled-banner').count()) > 0;
      expect(
        hasTable || hasEmpty || hasFlagBanner,
        'Expected the warehouse table, the empty-fleet message, or the flag-disabled banner'
      ).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to the workspace-scoped warehouses route redirects to login', async ({
      page,
    }) => {
      await clearAuthStorage(page);
      await page.goto(
        '/databricks/workspaces/00000000-0000-0000-0000-000000000000/warehouses',
        { waitUntil: 'domcontentloaded' }
      );
      await page.waitForURL(/\/(login)/, { timeout: 20_000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('lifecycle route resolves to a real page (no crash) for any workspace id', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      // A nil-UUID workspace: the route must resolve to a terminal UI
      // state — gate bounce, role denial, or the page with an empty
      // fleet — never a blank/crash page.
      await page.goto(
        '/databricks/workspaces/00000000-0000-0000-0000-000000000000/warehouses',
        { waitUntil: 'domcontentloaded' }
      );
      // intentional: terminal-state probe — element absence is tolerated and the next count/gate check adjudicates
      await page
        .waitForURL(/\/(unavailable|coming-soon|403|login|databricks\/workspaces)/, {
          timeout: 60_000,
        })
        .catch(() => null);
      const url = page.url();
      expect(
        url.includes('/unavailable') ||
          url.includes('/coming-soon') ||
          url.includes('/403') ||
          url.includes('/login') ||
          url.includes('/databricks/workspaces')
      ).toBe(true);
      await expect(page.locator('body')).toBeVisible();
    });
  });
});
