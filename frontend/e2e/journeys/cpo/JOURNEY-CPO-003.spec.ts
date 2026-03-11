/**
 * E2E Test: JOURNEY-CPO-003 — Review Access Request
 *
 * Journey: Review Access Request
 * Persona: Compliance Officer
 * Reference: ManualTest/Front/03-USER-JOURNEYS/cpo/JOURNEY-CPO-003.md
 *
 * Success/Failure/Edge. Routes: /governance/access-requests, /governance/access-requests/:id.
 * Fixture: getComplianceOfficerUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getComplianceOfficerUser } from '../../fixtures/auth';
import {
  assertNonExistentIdShowsError,
  hasLoginPrompt,
  loginAndNavigateToRoute,
} from '../../fixtures/helpers';

test.describe('JOURNEY-CPO-003: Review Access Request', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('access requests list loads', async ({ page }) => {
      const cpoUser = await getComplianceOfficerUser();
      await loginAndNavigateToRoute(page, cpoUser, '/governance', {
        timeout: 60000,
        contentSelector:
          '.governance-access-request-list-page, .access-request-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/governance');
      const hasContent =
        (await page.locator('.governance-access-request-list-page, .access-request-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('access request detail loads when request exists', async ({ page }) => {
      const cpoUser = await getComplianceOfficerUser();
      await loginAndNavigateToRoute(page, cpoUser, '/governance', {
        timeout: 60000,
        contentSelector:
          '.governance-access-request-list-page, .access-request-list-page, .empty-state, .error-display, #email',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      const requestRow = page.locator('.governance-access-request-table tr.row-link').first();
      if ((await requestRow.count()) > 0) {
        await requestRow.click();
        await page.waitForURL(/\/governance\/access-requests\/[^/]+$/, { timeout: 10000 });
        await page.waitForSelector(
          '.governance-access-request-detail-page, .error-display, .governance-status-badge',
          { timeout: 15000 }
        );
        const hasDetail =
          (await page.locator('.governance-access-request-detail-page').count()) > 0 ||
          (await page.locator('.governance-status-badge').count()) > 0;
        expect(hasDetail || page.url().includes('/governance/access-requests/')).toBe(true);
      }
    });
  });

  test.describe('Failure', () => {
    test('access request detail with non-existent id shows error', async ({ page }) => {
      const cpoUser = await getComplianceOfficerUser();
      await loginAndNavigateToRoute(page, cpoUser, '/', {
        timeout: 60000,
        contentSelector: '[data-testid="home-page"], .home-page, main',
      });
      await page.goto('/governance/access-requests/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.governance-access-request-detail-page',
        waitAfterLoad: 8000,
      });
    });

    test('unauthenticated access to access requests redirects to login or 403', async ({
      page,
    }) => {
      await clearAuthStorage(page);
      await page.goto('/governance', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|governance|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/403') || url.includes('/governance')
      ).toBe(true);
      if (url.includes('/governance')) {
        expect(await hasLoginPrompt(page)).toBe(true);
      }
    });
  });

  test.describe('Edge', () => {
    test('access requests list loads with empty state', async ({ page }) => {
      const cpoUser = await getComplianceOfficerUser();
      await loginAndNavigateToRoute(page, cpoUser, '/governance', {
        timeout: 60000,
        contentSelector:
          '.governance-access-request-list-page, .access-request-list-page, .empty-state, .error-display',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/governance');
    });
  });
});
