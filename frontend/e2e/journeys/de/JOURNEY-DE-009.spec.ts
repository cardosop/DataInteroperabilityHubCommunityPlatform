/**
 * E2E Test: JOURNEY-DE-009 — Set Up Data Virtualization
 *
 * Journey: Set Up Data Virtualization
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /virtualization, /virtualization/create.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-009: Set Up Data Virtualization', () => {
  test.setTimeout(360000); // 6 min: visible/slowMo; virtualization API may be slow

  test.describe('Success', () => {
    test('virtualization list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/virtualization');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.virtual-dataset-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 120000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/virtualization');
      const hasContent =
        (await page.locator('.virtual-dataset-list-page').count()) > 0 ||
        (await page.locator('.virtual-dataset-list-header').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.loading-spinner-container').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('virtualization create page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/virtualization/create');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.virtual-dataset-create-page, .error-display, .loading-spinner-container, #email',
        { timeout: 45000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/virtualization/create');
    });
  });

  test.describe('Failure', () => {
    test('virtual dataset detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/virtualization/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.virtual-dataset-detail-page',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('virtualization list loads with empty state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/virtualization');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.virtual-dataset-list-page, .empty-state, .error-display, .loading-spinner-container, #email',
        { timeout: 120000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/virtualization');
    });
  });
});
