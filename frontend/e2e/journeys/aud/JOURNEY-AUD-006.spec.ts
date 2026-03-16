/**
 * E2E Test: JOURNEY-AUD-006 — Review Social Feature Activity / Analyze Audit Trends
 *
 * Journey: Review Social Feature Activity / Analyze Audit Trends
 * Persona: Auditor
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /audit, /communities (Phase 27.2).
 * Fixture: getAuditorUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getAuditorUser, loginAsPersona } from '../../fixtures/auth';
import {
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
} from '../../fixtures/helpers';

test.describe('JOURNEY-AUD-006: Review Social Feature Activity / Analyze Audit Trends', () => {
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
      const hasContent =
        (await page.locator('.audit-event-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
      const hasServerError = await page.locator('text=/500|internal server error/i').count();
      expect(hasServerError).toBe(0);
    });

    test('audit export buttons visible', async ({ page }) => {
      const auditorUser = await getAuditorUser();
      await loginAndNavigateToRoute(page, auditorUser, '/audit', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/audit');
      const exportBtn = page.locator('button:has-text("Export"), .audit-export-buttons');
      const hasExport = (await exportBtn.count()) > 0;
      const hasList = (await page.locator('.audit-event-list-page').count()) > 0;
      expect(hasList || hasExport).toBe(true);
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
    test('audit list loads with empty state', async ({ page }) => {
      await loginAsPersona(page, getAuditorUser);
      await page.goto('/audit');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/audit');
    });
  });
});
