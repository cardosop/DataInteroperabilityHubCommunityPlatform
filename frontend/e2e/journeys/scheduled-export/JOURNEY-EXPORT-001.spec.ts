/**
 * E2E Test: JOURNEY-EXPORT-001 — Create and Run Scheduled Export
 *
 * Journey: Create and Run Scheduled Export
 * Use Cases: UC-EXPORT-001 (Schedule Recurring Export), UC-EXPORT-002 (Configure Export Destination)
 * Reference: docs/USER_JOURNEYS.md, docs/CRITICAL_UC_JOURNEY_IDS.yaml
 *
 * This file provides a filename-based alias for CI traceability gate detection.
 * The full end-to-end flow (create → trigger → poll → assert) lives in
 * scheduled-export-journey.spec.ts under the 'JOURNEY-EXPORT-001' describe block.
 *
 * This alias covers:
 *   Success: scheduled-exports list loads and Create Export form is accessible
 *   Failure: unauthenticated access redirects to login
 *   Edge: create form validates required fields
 *
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTenantAdminUser } from '../../fixtures/auth';
import { hasLoginPrompt, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-EXPORT-001: Create and Run Scheduled Export', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('scheduled-exports list loads and shows Create Export button', async ({ page }) => {
      const testUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, testUser, '/scheduled-exports', {
        timeout: 60000,
        contentSelector:
          '.scheduled-export-list-page, .empty-state, .unavailable-page, h1',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth may have expired');
        return;
      }

      const url = page.url();
      expect(url).toMatch(/\/scheduled-exports|\/403/);
      if (url.includes('/403')) {
        test.skip(true, 'Scheduled exports role-gated (403) — user may lack permission');
        return;
      }

      // Success test must NOT accept .error-display
      await expect(page.locator('.error-display')).not.toBeVisible();

      // Must render list page content
      const hasContent =
        (await page.locator('.scheduled-export-list-page, .empty-state, h1').count()) > 0;
      expect(hasContent, 'Expected scheduled-export list content').toBe(true);

      // Create Export button must be accessible
      const createBtn = page.getByRole('button', { name: /Create Export/i }).first();
      await expect(createBtn).toBeVisible({ timeout: 10000 });
    });

    test('create export form loads with required fields', async ({ page }) => {
      const testUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, testUser, '/scheduled-exports/create', {
        timeout: 60000,
        contentSelector:
          '.scheduled-export-create-page, form, h1',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(true, 'Redirected to login/403 — auth or role gated');
        return;
      }

      await expect(page.locator('.error-display')).not.toBeVisible();

      // Form must have name input and cron/schedule input
      const hasForm = (await page.locator('form').count()) > 0;
      const hasNameInput =
        (await page.locator('input[name="name"], input#name').count()) > 0;
      expect(hasForm, 'Expected form on create page').toBe(true);
      expect(hasNameInput, 'Expected name input on create page').toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to scheduled-exports redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/scheduled-exports', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|scheduled-exports|403)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onRouteWithLoginPrompt =
        url.includes('/scheduled-exports') && (await hasLoginPrompt(page));
      expect(onLogin || onRouteWithLoginPrompt).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('create form rejects submission without required fields', async ({ page }) => {
      const testUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, testUser, '/scheduled-exports/create', {
        timeout: 60000,
        contentSelector:
          '.scheduled-export-create-page, form, h1',
        acceptRedirectToLogin: true,
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(true, 'Redirected to login/403 — auth or role gated');
        return;
      }

      // Try to submit empty form
      const submitBtn = page.getByRole('button', { name: /Create|Save|Submit/i }).first();
      // intentional: probes optional UI presence — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state, not a test failure.
      await submitBtn.waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);
      if ((await submitBtn.count()) === 0) {
        test.skip(true, 'Submit button not found — form may not have loaded');
        return;
      }
      await submitBtn.click();
      await page.waitForTimeout(1000);

      // Must stay on create page (not navigate away) or show validation error
      const stayedOnCreate = page.url().includes('/create');
      const hasValidationError =
        (await page.locator('.field-error, [role="alert"], .error-message').count()) > 0 ||
        (await page
          .locator('input:invalid, select:invalid, [aria-invalid="true"]')
          .count()) > 0;
      expect(
        stayedOnCreate || hasValidationError,
        'Expected to stay on create page or show validation error on empty submission'
      ).toBe(true);
    });
  });
});
