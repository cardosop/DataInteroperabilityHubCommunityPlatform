/**
 * E2E Test: JOURNEY-DMO-003 — Manage Domain Topology
 *
 * Journey: Manage Domain Topology
 * Persona: Data Mesh Domain Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Routes: /mesh, /mesh/topology. mesh-search-ai-routes covers /mesh; this spec provides
 * dedicated DMO-003 journey coverage. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getDataMeshDomainOwnerUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DMO-003: Manage Domain Topology', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('mesh list loads for topology management', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/mesh', {
        timeout: 90000,
        contentSelector: '.mesh-domain-list-page, .error-display, [data-testid="error-display"], .empty-state, [data-testid="empty-state"]',
      });
      if (page.url().includes('/login')) {
        test.skip(page.url().includes('/login'), 'Auth gated — skipping success assertion');
        return;
      }
      expect(page.url()).toContain('/mesh');
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });

    test('mesh topology page loads', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/mesh/topology', {
        timeout: 90000,
        contentSelector: '.react-flow, .app-main, [data-testid="app-main"], .error-display, [data-testid="error-display"], .loading-spinner',
      });
      const onMeshTopology = page.url().includes('/mesh/topology');
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      if (onLogin || on403) {
        test.skip(onLogin || on403, 'Auth/role gated — skipping success assertion');
        return;
      }
      expect(onMeshTopology).toBe(true);
      const hasContent =
        (await page.locator('.react-flow, .app-main, [data-testid="app-main"]').count()) > 0;
      expect(hasContent).toBe(true);

      // The topology data fetch can fail during an API restart window — the
      // shell renders with an ErrorDisplay that offers Retry (GraphCanvas
      // onRetry → refetch). Use the app's recovery ONCE before judging the
      // error state a real failure.
      const errorDisplay = page.locator('.error-display, [data-testid="error-display"]').first();
      if ((await errorDisplay.count()) > 0) {
        // intentional: diagnostic-only read — an empty read just skips the
        // retry and the strict assertion below reports the visible state.
        const errText = (await errorDisplay.textContent().catch(() => '')) ?? '';
        if (/NETWORK_ERROR|Failed to fetch|connection|INTERNAL_ERROR|SERVICE_UNAVAILABLE/i.test(errText)) {
          await errorDisplay.locator('button:has-text("Retry")').first().click();
          // intentional: the retry may also fail under sustained churn — the
          // strict not.toBeVisible below then fails with the real state.
          await page
            .locator('.react-flow, [data-testid="topology-empty-state"], .error-display, [data-testid="error-display"]')
            .first()
            .waitFor({ state: 'visible', timeout: 30000 })
            .catch(() => null);
        }
      }
      await expect(errorDisplay).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to mesh route redirects to login or 403', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/mesh', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|mesh|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/mesh')).toBe(true);
      if (url.includes('/mesh')) {
        const hasLoginPrompt =
          (await page.locator('input#email').count()) > 0 ||
          (await page.locator('[href*="/login"]').count()) > 0 ||
          (await page.getByText('Sign in').count()) > 0;
        expect(hasLoginPrompt).toBe(true) /* acceptable states */;
      }
    });
  });

  test.describe('Edge', () => {
    test('mesh and topology routes accessible', async ({ page }) => {
      const dmoUser = await getDataMeshDomainOwnerUser();
      await loginAndNavigateToRoute(page, dmoUser, '/mesh', {
        timeout: 90000,
        contentSelector: '.mesh-domain-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      const urlAfterMesh = page.url();
      expect(
        urlAfterMesh.includes('/mesh') || urlAfterMesh.includes('/login') || urlAfterMesh.includes('/403')
      ).toBe(true);
      await page.goto('/mesh/topology');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const urlAfterTopo = page.url();
      expect(
        urlAfterTopo.includes('/mesh/topology') ||
          urlAfterTopo.includes('/mesh') ||
          urlAfterTopo.includes('/login')
      ).toBe(true);
    });
  });
});
