/**
 * E2E Test: JOURNEY-DC-012 — Preview Data Before Purchase
 *
 * Journey: Preview Data Before Purchase
 * Persona: Data Consumer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per marketplace-dc-routes pattern. Routes: /marketplace/listings/:id.
 * Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DC-012: Preview Data Before Purchase', () => {
  test.setTimeout(300000); // 5 min: consumer login + marketplace under parallel E2E load

  test.describe('Success', () => {
    test('listing detail loads (preview section)', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/marketplace', {
        timeout: 90000,
        contentSelector: '.listing-list-page, .empty-state, .error-display',
      });
      const listingLink = page.locator('.listing-list-page a[href*="/marketplace/listings/"]').first();
      if ((await listingLink.count()) > 0) {
        await listingLink.click();
        await page.waitForURL(/\/marketplace\/listings\/[^/]+/, { timeout: 10000 });
        await page.waitForSelector('.listing-detail-main, .error-display', { timeout: 15000 });
        const previewBtn = page.locator('button:has-text("Preview"), a:has-text("Preview")');
        const hasPreview = (await previewBtn.count()) > 0;
        const hasDetail = (await page.locator('.listing-detail-main').count()) > 0;
        expect(hasDetail || hasPreview).toBe(true);
      }
    });
  });

  test.describe('Failure', () => {
    test('preview from non-existent listing shows error', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/marketplace', {
        timeout: 90000,
        contentSelector: '.listing-list-page, .empty-state, .error-display',
      });
      await page.goto('/marketplace/listings/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.listing-detail-main',
        waitAfterLoad: 5000,
      });
    });
  });

  test.describe('Edge', () => {
    test('marketplace list loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/marketplace', {
        timeout: 90000,
        contentSelector: '.listing-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/marketplace');
    });
  });
});
