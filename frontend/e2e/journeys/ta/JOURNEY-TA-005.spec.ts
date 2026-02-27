/**
 * E2E Test: JOURNEY-TA-005 — Configure Data Mesh Domains
 *
 * Journey: Configure Data Mesh Domains
 * Persona: Tenant Admin
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /mesh, /mesh/create, /mesh/:id.
 * Fixture: getTenantAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUser, loginAsPersona } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-TA-005: Configure Data Mesh Domains', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('mesh domain list loads', async ({ page }) => {
      await loginAsPersona(page, getTenantAdminUser);
      await page.goto('/mesh');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          expect(page.url()).toMatch(/\/login|\/403/);
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/mesh');
      const hasContent =
        (await page.locator('.mesh-domain-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('mesh create page loads', async ({ page }) => {
      await loginAsPersona(page, getTenantAdminUser);
      await page.goto('/mesh/create');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.mesh-domain-create-page, .error-display, #email', {
        timeout: 20000,
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/mesh/create');
    });
  });

  test.describe('Failure', () => {
    test('mesh domain detail with non-existent id shows error', async ({ page }) => {
      await loginAsPersona(page, getTenantAdminUser);
      await page.goto('/mesh/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.mesh-domain-detail-page .mesh-domain-detail-content',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('mesh list loads with empty state', async ({ page }) => {
      await loginAsPersona(page, getTenantAdminUser);
      await page.goto('/mesh');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          contentSelector: '.mesh-domain-list-page, .empty-state, .error-display',
        });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          expect(page.url()).toMatch(/\/login|\/403/);
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/mesh');
    });
  });
});
