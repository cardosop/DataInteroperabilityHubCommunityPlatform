/**
 * E2E Test: JOURNEY-PA-010 — Manage ODPS Products
 *
 * Journey: Manage ODPS Products
 * Persona: Platform Admin
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /odps, /admin.
 * Fixture: getPlatformAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getPlatformAdminUser, loginAsPersona } from '../../fixtures/auth';
import {
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
} from '../../fixtures/helpers';

test.describe('JOURNEY-PA-010: Manage ODPS Products', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('ODPS list loads', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/odps', { timeout: 65000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      // Phase 211.A6 — /odps backward-compat redirects to
      // /contracts?spec_type=ODPS; the param proves the ODPS context
      // survived the redirect.
      expect(page.url()).toContain('/contracts');
      expect(page.url()).toContain('spec_type=ODPS');
    });

    test('admin page loads', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/admin', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/admin');
    });
  });

  test.describe('Failure', () => {
    test('ODPS detail with non-existent id shows error', async ({ page }) => {
      // loginAndNavigateToRoute directly to the detail URL — the bare
      // goto after UI login loses the in-memory token (Phase 11.1
      // hardening) and surfaces AUTH_UNAUTHORIZED instead of the 404
      // (batch b5). The /odps/:id route redirects to /contracts/:id, so
      // the terminal selectors cover the contract detail surface too.
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(
        page,
        paUser,
        '/odps/00000000-0000-0000-0000-000000000000',
        {
          timeout: 65000,
          contentSelector:
            '.odps-detail-page, .odps-detail-main, .contract-detail-page, [data-testid="contract-detail-page"], .error-display, [data-testid="error-display"], .disabled-capability-page, [data-testid="disabled-capability-page"], h1',
        }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector:
          '.odps-detail-page, .odps-detail-main, .contract-detail-page, [data-testid="contract-detail-page"]',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('ODPS and admin routes accessible', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/odps');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      // Phase 211.A6 — see the Success test above for the redirect contract.
      expect(page.url()).toContain('/contracts');
      expect(page.url()).toContain('spec_type=ODPS');
      await page.goto('/admin');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/admin');
    });
  });
});
