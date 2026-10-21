/**
 * E2E Test: JOURNEY-DB-006 — Inspect Table Permissions
 *
 * Persona: Data Engineer (TENANT_ADMIN-gated route)
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-006.md
 *
 * Real backend, deterministic: the e2e user has NO Databricks OBO
 * binding, so the table-detail permissions call fails closed with
 * 502 DATABRICKS_OBO_REFRESH_FAILED — the shipped P1 contract the UI
 * must surface (zero network calls to Databricks, never a service
 * fallback). The seeded mirror chain comes from ensure_e2e_user_roles.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUserOrTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DB-006: Inspect Table Permissions', () => {
  test.setTimeout(180000);

  test.describe('Failure (fail-closed)', () => {
    test('table detail surfaces DATABRICKS_OBO_REFRESH_FAILED without a binding', async ({
      page,
    }) => {
      const user = await getTenantAdminUserOrTestUser();
      await loginAndNavigateToRoute(page, user, '/databricks', {
        timeout: 60000,
        contentSelector: [
          '.warehouse-list',
          '[data-testid="databricks-flag-disabled"]',
          '.error-display, [data-testid="error-display"]',
        ].join(', '),
      });

      // Pin the seeded workspace row — .first() can hit e2e-journey-*
      // residue rows from DB-001 wizard runs (empty UC mirror → the
      // e2e_main drill below times out).
      await page
        .locator('tr', { hasText: 'e2e-databricks' })
        .getByTestId('databricks-browse-catalog')
        .first()
        .click();
      await expect(page.getByTestId('catalog-browser-page')).toBeVisible({
        timeout: 30000,
      });
      await page.getByRole('button', { name: /e2e_main/ }).click();
      await page.getByRole('button', { name: /e2e_main\.e2e_sales/ }).click();
      await page
        .getByRole('button', { name: /e2e_main\.e2e_sales\.e2e_orders/ })
        .click();

      // The permissions lookup fails closed: the UI renders the
      // machine-readable code — operators search runbooks by it.
      await expect(page.getByTestId('uc-detail-error')).toContainText(
        'DATABRICKS_OBO_REFRESH_FAILED',
        { timeout: 30000 }
      );
    });
  });
});
