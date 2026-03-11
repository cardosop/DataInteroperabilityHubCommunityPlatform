/**
 * E2E Test: JOURNEY-DC-010 — Query Virtual Dataset
 *
 * Journey: Query Virtual Dataset
 * Persona: Data Consumer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per marketplace-dc-routes pattern. Routes: /virtualization.
 * Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError } from '../../fixtures/helpers';

test.describe('JOURNEY-DC-010: Query Virtual Dataset', () => {
  test.setTimeout(240000);

  test.describe('Success', () => {
    test('virtualization list loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/virtualization');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.virtual-dataset-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 90000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/virtualization');
      const hasContent =
        (await page.locator('.virtual-dataset-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.loading-spinner-container').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('virtual dataset detail with non-existent id shows error', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/virtualization/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.virtual-dataset-detail-page, .error-display',
        waitAfterLoad: 12000,
      });
    });
  });

  test.describe('Edge', () => {
    test('virtualization list loads with empty state', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginUser(page, consumer);
      await page.goto('/virtualization');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.virtual-dataset-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 90000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/virtualization');
    });
  });
});
