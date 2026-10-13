/**
 * Phase 227 Wave 1 (227.L5.14) — TENANT_ADMIN contract-health triage E2E.
 *
 * Walks the admin's structureless-contract triage flow:
 * 1. TENANT_ADMIN navigates to /admin/contract-health.
 * 2. Page lists every structureless contract in the tenant.
 * 3. Each row's "Open Schema editor" link points at
 *    ``/contracts/{id}/edit?tab=schema`` and is reachable.
 *
 * Wave 1 staging starts with a clean DB so the empty state is the
 * common case. The test asserts EITHER the empty-state OR that any
 * row's Schema-editor link resolves correctly.
 */
import { expect, test } from '@playwright/test';

import { getTenantAdminUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Feature: Contract health admin (Phase 227 L5)', () => {
  test('admin can reach the contract-health page and follow a row link', async ({ page }) => {
    // The /admin/contract-health route is TENANT_ADMIN-gated — logging in
    // as the plain test user made the page unreachable and the spec always
    // took the "role not granted" skip (b7: counted among the 26 skips).
    // Use the admin persona so the happy path actually runs. The persona
    // provably carries TENANT_ADMIN (verified against /auth/me/), so the
    // route gate redirecting would be a REAL regression — assert strictly
    // instead of skipping. The churn-hardened navigation absorbs the
    // auth-init stalls that made the old raw-goto + 10s probe skip under
    // batch load (b7: the SPA sat on "Checking authentication…" >30s).
    const testUser = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, testUser, '/admin/contract-health', {
      timeout: 90000,
      contentSelector:
        '.contract-health-page, [data-testid="contract-health-page"], .error-display, [data-testid="error-display"], main',
      acceptRedirectToLogin: false,
    });

    const root = page.getByTestId('contract-health-page');
    await expect(root).toBeVisible({ timeout: 30000 });

    // Empty or populated — the table OR the empty state is present.
    const empty = page.getByTestId('contract-health-empty');
    const table = page.getByTestId('contract-health-table');
    const hasTable = (await table.count()) > 0;
    const hasEmpty = (await empty.count()) > 0;
    expect(hasTable || hasEmpty).toBe(true);

    if (hasTable) {
      // Pick the first row and confirm the deep-link href.
      const firstFix = page.locator('[data-testid^="contract-fix-"]').first();
      await expect(firstFix).toBeVisible({ timeout: 5000 });
      const href = await firstFix.getAttribute('href');
      expect(href).toContain('/edit?tab=schema');
    }
  });
});
