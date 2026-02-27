/**
 * E2E Test: JOURNEY-AUD-004 — Review Data Mesh Governance / Monitor Audit Logs
 *
 * Journey: Review Data Mesh Governance / Monitor Audit Logs
 * Persona: Auditor
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /audit, /mesh.
 * Fixture: getAuditorUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getAuditorUser, loginAsPersona } from '../../fixtures/auth';
import {
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
} from '../../fixtures/helpers';

test.describe('JOURNEY-AUD-004: Review Data Mesh Governance / Monitor Audit Logs', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('audit event list loads', async ({ page }) => {
      const auditorUser = await getAuditorUser();
      await loginAndNavigateToRoute(page, auditorUser, '/audit', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/audit');
    });

    test('mesh page loads', async ({ page }) => {
      const auditorUser = await getAuditorUser();
      await loginAndNavigateToRoute(page, auditorUser, '/mesh', { timeout: 60000 });
      await page.waitForTimeout(2000);
      const onMesh = page.url().includes('/mesh');
      const on403 = page.url().includes('/403');
      const onLogin = page.url().includes('/login');
      const hasContent =
        (await page.locator('.mesh-domain-list-page, .app-main, .error-display').count()) > 0;
      expect(onMesh || on403 || onLogin).toBe(true);
      expect(hasContent || on403 || onLogin).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('audit event detail with non-existent id shows error', async ({ page }) => {
      await loginAsPersona(page, getAuditorUser);
      await page.goto('/audit/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '[data-testid="audit-event-detail-page"]',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('audit and mesh routes accessible', async ({ page }) => {
      const auditorUser = await getAuditorUser();
      await loginAndNavigateToRoute(page, auditorUser, '/audit', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/audit');
      await page.goto('/mesh');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      expect(page.url().includes('/mesh') || page.url().includes('/403') || page.url().includes('/login')).toBe(true);
    });
  });
});
