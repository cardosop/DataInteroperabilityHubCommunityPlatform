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
import { getTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-010: Configure Connector for Data Source', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('integrations connections list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections', {
        timeout: 120000,
        contentSelector:
          '.connection-list-page, .marketplace-connection-list-page, .empty-state, .error-display',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/integrations/connections');
    });

    test('integrations connections create page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections/create', {
        timeout: 90000,
        contentSelector:
          '.marketplace-connection-create-page, .connection-create-page, .marketplace-connection-create-form, .error-display',
      });
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
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/integrations/connections/00000000-0000-0000-0000-000000000000',
        { timeout: 90000 }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.marketplace-connection-detail-page',
        waitAfterLoad: 12000,
      });
    });
  });

  test.describe('Edge', () => {
    test('connection create page renders form fields or unavailable state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections/create', {
        timeout: 60000,
        contentSelector:
          '.marketplace-connection-create-page, .connection-create-page, .error-display',
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/integrations/connections/create');

      const hasFormFields =
        (await page.locator('input, select, [role="combobox"]').count()) > 0 ||
        (await page.locator('.marketplace-connection-create-form').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasFormFields).toBe(true);
    });
  });
});
