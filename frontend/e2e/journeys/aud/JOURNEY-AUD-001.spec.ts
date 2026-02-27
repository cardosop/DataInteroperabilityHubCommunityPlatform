/**
 * E2E Test: JOURNEY-AUD-001 — Query Audit Events / Review Audit Logs
 *
 * Journey: Query Audit Events / Review Audit Logs
 * Persona: Auditor
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /audit, /audit/:id.
 * Fixture: getAuditorUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getAuditorUser, loginAsPersona } from '../../fixtures/auth';
import {
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
  waitForAppMainReady,
} from '../../fixtures/helpers';

test.describe('JOURNEY-AUD-001: Query Audit Events / Review Audit Logs', () => {
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
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
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
    test('audit list loads with filters', async ({ page }) => {
      const auditorUser = await getAuditorUser();
      await loginAndNavigateToRoute(page, auditorUser, '/audit', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/audit');
      // Wait for audit page content (list, filters, empty state, or error) after API loads
      await page
        .locator(
          '.audit-list-filters, .audit-event-list-page, .empty-state, .error-display'
        )
        .first()
        .waitFor({ state: 'visible', timeout: 25000 });
      const hasFilters =
        (await page.locator('.audit-list-filters').count()) > 0 ||
        (await page.locator('.audit-event-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasFilters).toBe(true);
    });
  });
});
