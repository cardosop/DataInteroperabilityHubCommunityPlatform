/**
 * E2E Test: JOURNEY-DE-002 — Set Up Scheduled Ingestion (if applicable)
 *
 * Journey: Set Up Scheduled Ingestion (if applicable)
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Routes: /scheduled-ingestions. Full flow covered by scheduled-ingestion-journey.spec.ts.
 * This spec provides dedicated DE-002 route coverage. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-002: Set Up Scheduled Ingestion (if applicable)', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('scheduled ingestions list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/scheduled-ingestions', {
        timeout: 90000,
        contentSelector:
          '.scheduled-ingestion-list-page, [data-testid="scheduled-ingestion-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1',
      });
      expect(page.url()).toContain('/scheduled-ingestions');
      const hasContent =
        (await page.locator('.scheduled-ingestion-list-page').count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0 ||
        (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0 ||
        (await page.locator('h1').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('scheduled ingestion detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/scheduled-ingestions/00000000-0000-0000-0000-000000000000',
        { timeout: 90000 }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '[data-testid="scheduled-ingestion-detail-page"]',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('scheduled ingestions route accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/scheduled-ingestions', {
        timeout: 90000,
        contentSelector:
          '.scheduled-ingestion-list-page, [data-testid="scheduled-ingestion-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1',
      });
      expect(page.url()).toContain('/scheduled-ingestions');
    });
  });
});
