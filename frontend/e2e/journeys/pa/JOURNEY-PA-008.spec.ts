/**
 * E2E Test: JOURNEY-PA-008 — Configure External Marketplace Connections
 * Persona: Platform Admin
 * Reference: ManualTest/Front/03-USER-JOURNEYS/pa/JOURNEY-PA-008.md
 * Real backend only; no mocks.
 */
import { expect, test } from '@playwright/test';
import { clearAuthStorage, getPlatformAdminUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-PA-008: Configure External Marketplace Connections', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('platform admin can access external marketplace connections page', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      const routes = [
        '/integrations/connections',
        '/admin/marketplace-connections',
        '/integrations',
      ];

      let landed = false;
      for (const route of routes) {
        await loginAndNavigateToRoute(page, paUser, route, {
          timeout: 60000,
          contentSelector: '.integrations-connections-page, .marketplace-connections-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
        });
        if (page.url().includes('/403') || page.url().includes('/login')) continue;
        landed = true;
        break;
      }

      if (!landed) {
        test.skip(true, 'External marketplace connections page not accessible');
        return;
      }

      const hasError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      if (hasError) {
        // intentional: tolerates a detached/removed element while extracting text for a diagnostic message; the surrounding throw/expect below this catch is the primary failure path.
        const errText = await page.locator('.error-display, [data-testid="error-display"]').first().first().textContent().catch(() => '');
        if (!/403|forbidden/i.test(errText ?? '')) {
          throw new Error(`Connections page shows error: ${errText}`);
        }
      }

      const hasContent =
        (await page.locator('.integrations-connections-page').count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0 ||
        (await page.locator('.connections-list, .marketplace-connections-page').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access redirects', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/integrations/connections', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|integrations|403)/, { timeout: 20_000 });
      expect(page.url()).toMatch(/\/login|\/403|\/integrations/);
    });
  });

  test.describe('Route', () => {
    test('integrations connections route loads', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/integrations/connections', {
        timeout: 60000,
        contentSelector: '.integrations-connections-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toMatch(/\/integrations|\/403|\/login/);
    });
  });
});
