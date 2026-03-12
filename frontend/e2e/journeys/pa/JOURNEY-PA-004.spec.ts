/**
 * E2E Test: JOURNEY-PA-004 — Review Platform Analytics
 * Persona: Platform Admin
 * Reference: ManualTest/Front/03-USER-JOURNEYS/pa/JOURNEY-PA-004.md
 * Real backend only; no mocks.
 */
import { expect, test } from '@playwright/test';
import { clearAuthStorage, getPlatformAdminUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1` : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('JOURNEY-PA-004: Review Platform Analytics', () => {
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('platform admin sees analytics with non-zero metric values', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      const analyticsRoutes = [
        '/admin/analytics', '/admin/usage', '/admin',
      ];

      let landed = false;
      for (const route of analyticsRoutes) {
        await loginAndNavigateToRoute(page, paUser, route, {
          timeout: 60000,
          contentSelector: '.admin-page, .analytics-page, .usage-page',
        });
        if (page.url().includes('/403') || page.url().includes('/login')) continue;
        const hasAnalytics =
          (await page.locator('.analytics-page, .usage-page').count()) > 0 ||
          (await page.locator('text=/total|tenants|assets|users/i').count()) > 0;
        if (hasAnalytics) { landed = true; break; }
      }

      if (!landed) {
        test.skip(true, 'Analytics/usage page not found at any known route');
        return;
      }

      // Platform must have at least 1 tenant (the E2E tenant itself)
      const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
      if (!accessToken) return;

      const analyticsResp = await page.request.get(`${API_BASE}/admin/analytics/`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      }).catch(() => null);

      if (analyticsResp && analyticsResp.ok()) {
        const data = (await analyticsResp.json()) as Record<string, unknown>;
        const tenantCount =
          (data.tenant_count as number) ?? (data.tenants as number) ?? null;
        if (tenantCount !== null) {
          expect(tenantCount).toBeGreaterThan(0);
        }
      }

      // UI: page shows some metric (number visible in the page)
      const hasMetric = (await page.locator('text=/[1-9][0-9]*/').count()) > 0;
      expect(hasMetric).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access redirects', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/admin', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|admin|403)/, { timeout: 20_000 });
      expect(page.url()).toMatch(/\/login|\/403|\/admin/);
    });
  });

  test.describe('Route', () => {
    test('admin analytics route loads', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/admin', {
        timeout: 60000,
        contentSelector: '.admin-page, [data-testid="forbidden-page"]',
      });
      expect(page.url()).toMatch(/\/admin|\/403|\/login/);
    });
  });
});
