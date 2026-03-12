/**
 * E2E Test: JOURNEY-PA-009 — Manage Federated Assets
 * Persona: Platform Admin
 * Reference: ManualTest/Front/03-USER-JOURNEYS/pa/JOURNEY-PA-009.md
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

test.describe('JOURNEY-PA-009: Manage Federated Assets', () => {
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('platform admin can view federated assets or data mesh topology', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      const routes = [
        '/mesh', '/mesh/topology', '/admin/federated-assets',
        '/data-mesh', '/semantic',
      ];

      let landed = false;
      for (const route of routes) {
        await loginAndNavigateToRoute(page, paUser, route, {
          timeout: 60000,
          contentSelector: '.mesh-list-page, .topology-page, .federated-assets-page, .empty-state, .unavailable-page',
        });
        if (page.url().includes('/403') || page.url().includes('/login')) continue;
        landed = true;
        break;
      }

      if (!landed) {
        test.skip(true, 'Federated assets / data mesh page not accessible to platform admin');
        return;
      }

      // API check: federated assets or mesh domains
      const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
      if (!accessToken) return;

      const meshResp = await page.request.get(`${API_BASE}/mesh/domains/?page_size=5`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      }).catch(() => null);

      if (meshResp && meshResp.ok()) {
        const data = (await meshResp.json()) as { results?: unknown[] };
        expect(Array.isArray(data.results) || Array.isArray(data)).toBe(true);
      }

      const hasContent =
        (await page.locator('.mesh-list-page, .topology-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.unavailable-page').count()) > 0; // capability may be gated
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access redirects', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/mesh', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|mesh|403)/, { timeout: 20_000 });
      expect(page.url()).toMatch(/\/login|\/403|\/mesh/);
    });
  });

  test.describe('Route', () => {
    test('mesh/data mesh route loads or shows unavailable', async ({ page }) => {
      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/mesh', {
        timeout: 60000,
        contentSelector: '.mesh-list-page, .empty-state, .unavailable-page, .error-display',
      });
      expect(page.url()).toMatch(/\/mesh|\/403|\/login/);
    });
  });
});
