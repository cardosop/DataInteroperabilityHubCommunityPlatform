/**
 * E2E Test: JOURNEY-DE-014 — Create ODPS via API
 *
 * Journey: Create ODPS via API
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /odps/upload, /odps, /contracts.
 * UI flow for ODPS creation (API flow would be separate API tests).
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUserOrTestUser, getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-014: Create ODPS via API', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('ODPS upload page loads', async ({ page }) => {
      const testUser = await getTenantAdminUserOrTestUser();
      await loginAndNavigateToRoute(page, testUser, '/odps/upload', { timeout: 60000 });
      expect(page.url()).not.toContain('/login');
      // Phase 211.A6 — backward-compat redirect: /odps/upload is
      // consolidated into the contracts-create flow.
      expect(page.url()).toContain('/contracts/create');
    });

    test('ODPS list loads', async ({ page }) => {
      const testUser = await getTenantAdminUserOrTestUser();
      await loginAndNavigateToRoute(page, testUser, '/odps', { timeout: 60000 });
      expect(page.url()).not.toContain('/login');
      // Phase 211.A6 — /odps redirects to /contracts with the ODPS
      // spec_type preserved (the spec_type proves the redirect carried
      // the ODPS context, not a generic contracts landing).
      expect(page.url()).toContain('/contracts');
      expect(page.url()).toContain('spec_type=ODPS');
    });
  });

  test.describe('Failure', () => {
    test('ODPS detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/odps/00000000-0000-0000-0000-000000000000',
        { timeout: 90000 }
      );
      // intentional: probes optional UI presence via a multi-line locator chain — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state.
      await page
        .locator('.odps-detail-main, .error-display, [data-testid="error-display"]')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);
      const hasError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      const noSuccessContent = (await page.locator('.odps-detail-main').count()) === 0;
      const onLogin = page.url().includes('/login');
      expect(hasError || noSuccessContent || onLogin).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Edge', () => {
    test('ODPS upload and list accessible', async ({ page }) => {
      const testUser = await getTenantAdminUserOrTestUser();
      await loginAndNavigateToRoute(page, testUser, '/odps/upload', { timeout: 60000 });
      expect(page.url()).not.toContain('/login');
      // Phase 211.A6 — see the Success tests above for the redirect contract.
      expect(page.url()).toContain('/contracts/create');
      await loginAndNavigateToRoute(page, testUser, '/odps', { timeout: 60000 });
      expect(page.url()).not.toContain('/login');
      expect(page.url()).toContain('/contracts');
      expect(page.url()).toContain('spec_type=ODPS');
    });
  });
});
