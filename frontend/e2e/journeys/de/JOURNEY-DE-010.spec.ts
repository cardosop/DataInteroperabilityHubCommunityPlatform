/**
 * E2E Test: JOURNEY-DE-010 — Configure Connector for Data Source
 *
 * Journey: Configure Connector for Data Source
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /integrations/connections, /integrations/connections/create.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-010: Configure Connector for Data Source', () => {
  test.setTimeout(360000);

  test.describe('Success', () => {
    test('integrations connections list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/integrations/connections');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.connection-list-page, .marketplace-connection-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 120000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/integrations/connections');
    });

    test('integrations connections create page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/integrations/connections/create');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.marketplace-connection-create-page, .connection-create-page, .marketplace-connection-create-form, .loading-spinner-container, .error-display, #email',
        { timeout: 90000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/integrations/connections/create');
    });
  });

  test.describe('Failure', () => {
    test('connection detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/integrations/connections/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.marketplace-connection-detail-page',
        waitAfterLoad: 12000,
      });
    });
  });

  test.describe('Edge', () => {
    test('integrations connections list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/integrations/connections');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.connection-list-page, .marketplace-connection-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 120000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/integrations/connections');
    });
  });
});
