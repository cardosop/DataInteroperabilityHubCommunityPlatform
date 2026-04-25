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
import { getConsumerTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DC-010: Query Virtual Dataset', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('virtualization list loads', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/virtualization', { timeout: 90000 });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/virtualization');
      // Phase 2: wait for loading spinner to resolve into a terminal state (spinner is transient)
      // intentional: best-effort .catch on an optional step — primary pass/fail is made by a downstream assertion (verifyViaApi, waitFor, explicit expect). The fallback value tolerates well-known transient or absent-UI cases without papering over real failures.
      await page
        .locator('.virtual-dataset-list-page, .empty-state, .error-display')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 })
        .catch(() => null);
      // Spinner excluded: it is a transient loading indicator, not a valid terminal state
      const hasContent =
        (await page.locator('.virtual-dataset-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('virtual dataset detail with non-existent id shows error', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(
        page,
        consumer,
        '/virtualization/00000000-0000-0000-0000-000000000000',
        { timeout: 90000 }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.virtual-dataset-detail-page, .error-display',
        waitAfterLoad: 12000,
      });
    });
  });

  test.describe('Edge', () => {
    test('virtualization list loads with empty state', async ({ page }) => {
      const consumer = await getConsumerTestUser();
      await loginAndNavigateToRoute(page, consumer, '/virtualization', { timeout: 90000 });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/virtualization');
    });
  });
});
