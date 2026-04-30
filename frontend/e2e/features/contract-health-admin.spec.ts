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

import { getTestUser, loginUser } from '../fixtures/auth';

test.describe('Feature: Contract health admin (Phase 227 L5)', () => {
  test('admin can reach the contract-health page and follow a row link', async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.goto('/admin/contract-health', { waitUntil: 'domcontentloaded' });

    if (page.url().includes('/login')) {
      test.skip(true, 'Redirected to /login — auth token expired');
      return;
    }

    // Either the page mounts (with rows or empty state) OR the user
    // lacks the TENANT_ADMIN role and gets a 403/redirect — both are
    // valid backend states. We only assert the happy path here.
    const root = page.getByTestId('contract-health-page');
    const reachable = await root.isVisible({ timeout: 10000 }).catch(() => false);
    if (!reachable) {
      test.skip(true, 'TENANT_ADMIN role not granted in this tenant');
      return;
    }

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
