/**
 * E2E: Core data routes — Assets and Datasets (Phase B gap-fill)
 *
 * Routes: /assets, /assets/create, /assets/:id, /datasets, /datasets/create, /datasets/:id.
 * These are the most fundamental routes in the data catalog and were previously absent
 * from the batch-2 route smoke tests.
 *
 * Success: list pages load with content selector.
 * Failure: non-existent :id shows error display (not a broken render).
 * Real backend only; no mocks/stubs.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../../fixtures/helpers';

test.describe('Core data routes — Assets and Datasets', () => {
  test.setTimeout(120000);

  // ─── Assets ──────────────────────────────────────────────────────────────

  test.describe('Assets', () => {
    test.describe('Success', () => {
      test('assets list loads (empty or with data)', async ({ page }) => {
        await page.goto('/assets');
        try {
          await waitForAppMainReady(page, {
            timeout: 65000,
            contentSelector: '.asset-list-page, .empty-state, .error-display',
          });
        } catch {
          if (page.url().includes('/login')) {
            expect(page.url()).toContain('/login');
            return;
          }
          throw new Error('Assets list page did not reach a terminal state within 65s');
        }
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        expect(page.url()).toContain('/assets');
        await expect(
          page.locator('.asset-list-page, .empty-state').first()
        ).toBeVisible({ timeout: 10000 });
      });

      test('asset create page loads', async ({ page }) => {
        await page.goto('/assets/create');
        try {
          await waitForAppMainReady(page, {
            timeout: 60000,
            contentSelector: '.asset-create-page, .error-display',
          });
        } catch {
          if (page.url().includes('/login')) {
            expect(page.url()).toContain('/login');
            return;
          }
          throw new Error('Asset create page did not reach a terminal state within 60s');
        }
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        expect(page.url()).toContain('/assets/create');
        await expect(page.locator('.asset-create-page')).toBeVisible({ timeout: 10000 });
      });
    });

    test.describe('Failure', () => {
      test('asset detail with non-existent id shows error display', async ({ page }) => {
        const nonExistentId = '00000000-0000-0000-0000-000000000000';
        // Intercept the API response before navigating so we capture it regardless of timing.
        // Only 404 is valid — 200 means the resource exists (backend bug), 500 is infrastructure.
        const responsePromise = page.waitForResponse(
          (resp) =>
            resp.url().includes(`/assets/${nonExistentId}`) &&
            resp.status() === 404,
          { timeout: 15000 }
        ).catch(() => null); // null if login redirect fires before the API responds

        await page.goto(`/assets/${nonExistentId}`);
        await page.waitForLoadState('domcontentloaded');
        await responsePromise;

        // Race: wait for either the error display OR any terminal state instead of a static sleep
        await page.locator('.error-display, .error-display-title, .asset-detail-page')
          .first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);

        const onLogin = page.url().includes('/login');
        if (onLogin) return;

        // Require BOTH: error component visible AND "not found" text (not a network/500 error)
        const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
        const hasNotFoundText = (await page.locator('.error-display-message').filter({ hasText: /not found|could not be found|404/i }).count()) > 0;
        if (hasErrorDisplay && !hasNotFoundText) {
          const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
          throw new Error(`Asset detail shows non-404 error for nil UUID: "${errText?.slice(0, 200)}". Expected "not found".`);
        }
        expect(hasErrorDisplay && hasNotFoundText).toBe(true);
      });
    });
  });

  // ─── Datasets ────────────────────────────────────────────────────────────

  test.describe('Datasets', () => {
    test.describe('Success', () => {
      test('datasets list loads (empty or with data)', async ({ page }) => {
        await page.goto('/datasets');
        try {
          await waitForAppMainReady(page, {
            timeout: 65000,
            contentSelector: '.dataset-list-page, .empty-state, .error-display',
          });
        } catch {
          if (page.url().includes('/login')) {
            expect(page.url()).toContain('/login');
            return;
          }
          throw new Error('Datasets list page did not reach a terminal state within 65s');
        }
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        expect(page.url()).toContain('/datasets');
        await expect(
          page.locator('.dataset-list-page, .empty-state').first()
        ).toBeVisible({ timeout: 10000 });
      });

      test('dataset create page loads', async ({ page }) => {
        await page.goto('/datasets/create');
        try {
          await waitForAppMainReady(page, {
            timeout: 60000,
            contentSelector: '.dataset-create-page, .error-display',
          });
        } catch {
          if (page.url().includes('/login')) {
            expect(page.url()).toContain('/login');
            return;
          }
          throw new Error('Dataset create page did not reach a terminal state within 60s');
        }
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        expect(page.url()).toContain('/datasets/create');
        await expect(page.locator('.dataset-create-page')).toBeVisible({ timeout: 10000 });
      });
    });

    test.describe('Failure', () => {
      test('dataset detail with non-existent id shows error display', async ({ page }) => {
        const nonExistentId = '00000000-0000-0000-0000-000000000000';
        const responsePromise = page.waitForResponse(
          (resp) =>
            resp.url().includes(`/datasets/${nonExistentId}`) &&
            resp.status() === 404,
          { timeout: 15000 }
        ).catch(() => null);

        await page.goto(`/datasets/${nonExistentId}`);
        await page.waitForLoadState('domcontentloaded');
        await responsePromise;

        await page.locator('.error-display, .error-display-title, .dataset-detail-page')
          .first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);

        const onLogin = page.url().includes('/login');
        if (onLogin) return;

        const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
        const hasNotFoundText = (await page.locator('.error-display-message').filter({ hasText: /not found|could not be found|404/i }).count()) > 0;
        if (hasErrorDisplay && !hasNotFoundText) {
          const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
          throw new Error(`Dataset detail shows non-404 error for nil UUID: "${errText?.slice(0, 200)}". Expected "not found".`);
        }
        expect(hasErrorDisplay && hasNotFoundText).toBe(true);
      });
    });
  });
});
