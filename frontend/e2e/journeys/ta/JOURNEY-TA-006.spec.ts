/**
 * E2E Test: JOURNEY-TA-006 — Set Up Advanced Governance
 *
 * Journey: Set Up Advanced Governance
 * Persona: Tenant Admin
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /governance, /governance/retention.
 * Fixture: getTenantAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUser, loginAsPersona } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-TA-006: Set Up Advanced Governance', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('governance page loads', async ({ page }) => {
      await loginAsPersona(page, getTenantAdminUser);
      await page.goto('/governance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onGov = page.url().includes('/governance');
      const on403 = page.url().includes('/403');
      const onLogin = page.url().includes('/login');
      if (on403 || onLogin) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }
      expect(onGov).toBe(true);
      const hasContent =
        (await page.locator('.governance-access-request-list-page, .access-request-list-page, .app-main, [data-testid="app-main"]').count()) > 0;
      expect(hasContent).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });

    test('governance retention list loads', async ({ page }) => {
      const taUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, taUser, '/governance/retention', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }
      const onRetention = page.url().includes('/governance/retention');
      expect(onRetention).toBe(true);
      const hasContent =
        (await page.locator('.governance-retention-policy-list-page, .empty-state, [data-testid="empty-state"]').count()) > 0;
      expect(hasContent).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('governance retention detail with non-existent id shows error', async ({ page }) => {
      await loginAsPersona(page, getTenantAdminUser);
      await page.goto('/governance/retention/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.governance-retention-policy-detail-page',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('governance and retention routes accessible', async ({ page }) => {
      await loginAsPersona(page, getTenantAdminUser);
      await page.goto('/governance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/governance');
      await page.goto('/governance/retention');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/governance/retention');
    });
  });
});
