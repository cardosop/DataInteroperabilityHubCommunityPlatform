/**
 * E2E Test: JOURNEY-DA-003 — Query Virtual Dataset
 *
 * Journey: Query Virtual Dataset
 * Persona: Data Analyst
 * Reference: docs/USER_JOURNEYS.md
 *
 * Routes: /virtualization. mesh-search-ai-routes covers virtualization; this spec provides
 * dedicated DA-003 journey coverage. Fixture: getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DA-003: Query Virtual Dataset', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('virtualization list loads (virtual datasets or empty)', async ({ page }) => {
      const da = await getConsumerTestUser();
      await loginUser(page, da);
      await page.goto('/virtualization');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.virtual-dataset-list-page, .empty-state',
        { timeout: 65000 }
      );
      if (page.url().includes('/login') || page.url().includes('/403')) {
        throw new Error(`Unexpected redirect to ${page.url()} — verify DA user has virtualization access`);
      }
      expect(page.url()).toContain('/virtualization');
      await expect(page.locator('.error-display')).not.toBeVisible();
      const hasContent =
        (await page.locator('.virtual-dataset-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('virtualization detail with non-existent id shows error', async ({ page }) => {
      const da = await getConsumerTestUser();
      await loginUser(page, da);
      await page.goto('/virtualization/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.virtual-dataset-detail-page',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('virtualization route accessible', async ({ page }) => {
      const da = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, da, '/virtualization', {
        timeout: 60000,
        contentSelector: '.virtual-dataset-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/virtualization');
    });
  });
});
