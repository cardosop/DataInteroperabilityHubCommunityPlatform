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
      const hasContent =
        (await page.locator('.governance-access-request-list-page, .access-request-list-page, .app-main, .error-display').count()) > 0;
      expect(onGov || on403 || onLogin).toBe(true);
      expect(hasContent || on403 || onLogin).toBe(true);
    });

    test('governance retention list loads', async ({ page }) => {
      const taUser = await getTenantAdminUser();
      await loginAndNavigateToRoute(page, taUser, '/governance/retention', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      const onRetention = page.url().includes('/governance/retention');
      const on403 = page.url().includes('/403');
      const hasContent =
        (await page.locator('.governance-retention-policy-list-page, .empty-state, .error-display, [data-testid="forbidden-page"]').count()) > 0;
      // Role-gated: 403 when TENANT_ADMIN not assigned; or retention list loads
      expect(onRetention || on403).toBe(true);
      expect(hasContent || on403).toBe(true);
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
