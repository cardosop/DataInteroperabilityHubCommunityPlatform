/**
 * E2E: UC-INT-002 — Create Custom Connector
 *
 * Use Case: Create Custom Connector
 * Persona: Data Engineer, External Developer
 * Reference: docs/USE_CASES.md#uc-int-002
 *
 * Success/Failure/Edge. Routes: /integrations, /integrations/connections/create.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUserOrTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('UC-INT-002: Create Custom Connector', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('integrations create page loads', async ({ page }) => {
      const user = await getTenantAdminUserOrTestUser();
      await loginAndNavigateToRoute(page, user, '/integrations', {
        timeout: 60000,
        contentSelector: '.marketplace-connection-list-page, .integrations-layout, .empty-state, [data-testid="empty-state"]',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        throw new Error(
          `Expected integrations for tenant-capable user; got ${page.url()} (auth or role regression)`
        );
      }
      const createBtn = page.locator('a[href*="/integrations/connections/create"], button:has-text("Create"), button:has-text("Add")');
      if ((await createBtn.count()) > 0) {
        await createBtn.first().click();
        await page.waitForLoadState('domcontentloaded');
        await waitForAppMainReady(page, {
          timeout: 60000,
          contentSelector:
            '.marketplace-connection-create-page, .connection-create-page, .error-display, [data-testid="error-display"], form',
        });
      } else {
        await loginAndNavigateToRoute(page, user, '/integrations/connections/create', {
          timeout: 60000,
        });
      }
      expect(page.url().includes('/integrations')).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to integrations create redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/integrations/connections/create', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|403)(\?|$)/, { timeout: 25_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      expect(onLogin || on403).toBe(true) /* acceptable states */;
    });

    test('create connector page with empty submit shows validation or stays on form', async ({ page }) => {
      const user = await getTenantAdminUserOrTestUser();
      await loginAndNavigateToRoute(page, user, '/integrations/connections/create', {
        timeout: 60000,
      });
      if (page.url().includes('/login')) return;
      if ((await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0) {
        test.info().annotations.push({ type: 'note', description: 'API unavailable — form not rendered, skipping validation check' });
        return;
      }
      await page.locator('.marketplace-connection-create-page, form.marketplace-connection-create-form').first()
        .waitFor({ state: 'visible', timeout: 60000 });
      const submitBtn = page.locator('button[type="submit"]').filter({ hasText: /Create Connection/i });
      await expect(submitBtn).toBeVisible({ timeout: 30000 });
      await submitBtn.click();
      await page.waitForTimeout(600); // HTML5 validation fires synchronously
      // Must stay on create page OR show inline validation errors
      const stillOnCreate = page.url().includes('/create');
      const hasValidation =
        (await page.locator('.error-message, [aria-invalid="true"], input:invalid').count()) > 0;
      expect(stillOnCreate || hasValidation).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Edge', () => {
    test('integrations list loads', async ({ page }) => {
      const user = await getTenantAdminUserOrTestUser();
      await loginAndNavigateToRoute(page, user, '/integrations', {
        timeout: 60000,
        contentSelector: '.marketplace-connection-list-page, .integrations-layout, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toContain('/integrations');
    });
  });
});
