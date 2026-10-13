/**
 * E2E Test: JOURNEY-DB-005 — Browse the Unity Catalog
 *
 * Persona: Data Engineer (TENANT_ADMIN-gated route)
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-005.md
 *
 * Real backend, deterministic: the e2e provisioning
 * (ensure_e2e_user_roles, task 1.11) seeds a workspace
 * ("e2e-databricks") with a catalog → schema → table mirror chain for the
 * default e2e tenant. The spec drives the REAL browse flow: workspace
 * list → Browse catalog → drill → search — no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUserOrTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

const CATALOG_SELECTOR = [
  '[data-testid="catalog-browser-page"]',
  '.error-display, [data-testid="error-display"]',
].join(', ');

test.describe('JOURNEY-DB-005: Browse the Unity Catalog', () => {
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('workspace → catalog → schema → table drill with search', async ({ page }) => {
      const user = await getTenantAdminUserOrTestUser();
      await loginAndNavigateToRoute(page, user, '/databricks', {
        timeout: 60000,
        contentSelector: [
          '.warehouse-list',
          '[data-testid="databricks-register-wizard"]',
          '[data-testid="databricks-flag-disabled"]',
          '.error-display, [data-testid="error-display"]',
        ].join(', '),
      });

      // The seeded workspace row carries the browse affordance. Pin the
      // ROW to the seeded name — the management table can also list
      // e2e-journey-* residue rows created by DB-001 wizard runs, whose
      // UC mirror is empty (their browse link lands on a catalog browser
      // with zero rows and the drill below times out).
      const browse = page
        .locator('tr', { hasText: 'e2e-databricks' })
        .getByTestId('databricks-browse-catalog')
        .first();
      await expect(browse).toBeVisible({ timeout: 30000 });
      await browse.click();

      // The catalog browser renders with breadcrumbs + the seeded catalog.
      await expect(page.getByTestId('catalog-browser-page')).toBeVisible({
        timeout: 30000,
      });
      await expect(page.getByRole('navigation', { name: /breadcrumbs/i })).toBeVisible();
      await expect(page.getByRole('button', { name: /e2e_main/ })).toBeVisible({
        timeout: 30000,
      });

      // Search filters the listing client-side. Scope to the catalog
      // page — the app shell's global search input is also a searchbox
      // matching /search/i (strict-mode double match on fill).
      const search = page
        .getByTestId('catalog-browser-page')
        .getByRole('searchbox', { name: /search/i });
      await search.fill('e2e_m');
      await expect(page.getByRole('button', { name: /e2e_main/ })).toBeVisible();
      await search.fill('');

      // Drill: catalog → schema → table (real 1.3 endpoints).
      await page.getByRole('button', { name: /e2e_main/ }).click();
      await expect(
        page.getByRole('button', { name: /e2e_main\.e2e_sales/ })
      ).toBeVisible({ timeout: 30000 });
      await page.getByRole('button', { name: /e2e_main\.e2e_sales/ }).click();
      await expect(
        page.getByRole('button', { name: /e2e_main\.e2e_sales\.e2e_orders/ })
      ).toBeVisible({ timeout: 30000 });
    });
  });

  test.describe('Edge', () => {
    test('an unknown workspace surfaces the error envelope (no crash)', async ({ page }) => {
      const user = await getTenantAdminUserOrTestUser();
      await loginAndNavigateToRoute(
        page,
        user,
        '/databricks/workspaces/00000000-0000-0000-0000-000000000000/catalog',
        {
          timeout: 60000,
          contentSelector: CATALOG_SELECTOR,
        }
      );
      // The page renders its documented error surface (the backend 404
      // envelope) — never a blank screen or an uncaught exception.
      await expect(page.getByTestId('catalog-browse-error')).toBeVisible({
        timeout: 30000,
      });
    });
  });
});
