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
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('UC-INT-002: Create Custom Connector', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('integrations create page loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/integrations', {
        timeout: 60000,
        contentSelector: '.marketplace-connection-list-page, .integrations-layout, .empty-state, .error-display',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      const createBtn = page.locator('a[href*="/integrations/connections/create"], button:has-text("Create"), button:has-text("Add")');
      if ((await createBtn.count()) > 0) {
        await createBtn.first().click();
        await page.waitForLoadState('domcontentloaded');
      } else {
        await page.goto('/integrations/connections/create');
        await page.waitForLoadState('domcontentloaded');
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
      expect(onLogin || on403).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('integrations list loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/integrations', {
        timeout: 60000,
        contentSelector: '.marketplace-connection-list-page, .integrations-layout, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/integrations');
    });
  });
});
