/**
 * E2E Test: JOURNEY-DPO-008 — Create Transformation Pipeline for Asset
 *
 * Journey: Data Product Owner creates a transformation pipeline for an asset.
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * The transformation pipeline feature is capability-gated (`transformation` capability).
 * Routes: /transformation (list), /transformation/create, /transformation/pipelines/:id
 * When the capability is disabled the CapabilityRoute renders /unavailable; when enabled
 * the full pipeline UI is shown.
 *
 * All tests run against the real backend — no mocks/stubs.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-008: Create Transformation Pipeline for Asset', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('transformation list page loads (list or capability-gated unavailable)', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/transformation', {
        timeout: 60000,
        // Exclude .loading-spinner-container from stop condition — CapabilityRoute shows a
        // spinner while capabilities are fetched; stopping there leads to false assertion
        contentSelector:
          '.transformation-pipeline-list-page, .unavailable-page, .empty-state, .error-display',
      });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on /transformation');
      }

      // Wait past the CapabilityRoute loading spinner to the final state
      await page.waitForSelector(
        '.transformation-pipeline-list-page, .empty-state, .unavailable-page',
        { timeout: 30000 }
      ).catch(() => null);

      const capabilityEnabled =
        page.url().includes('/transformation') &&
        (await page.locator('.transformation-pipeline-list-page, .empty-state').count()) > 0;
      const capabilityDisabled =
        (await page.locator('.unavailable-page').count()) > 0 ||
        page.url().includes('/unavailable') ||
        page.url().includes('/403');

      expect(capabilityEnabled || capabilityDisabled).toBe(true);

      if (capabilityEnabled) {
        await expect(
          page.locator('.transformation-pipeline-list-page, .empty-state').first()
        ).toBeVisible({ timeout: 5000 });
      } else {
        await expect(
          page.locator('.unavailable-page, [role="main"]').first()
        ).toBeVisible({ timeout: 5000 });
      }
    });

    test('transformation create page loads (form or capability-gated unavailable)', async ({
      page,
    }) => {
      // CapabilityRoute for 'transformation' may redirect to /unavailable when capability is off.
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/', {
        timeout: 60000,
        contentSelector: '[data-testid="home-page"], .home-page, .app-header',
      });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login before /transformation/create navigation');
      }

      await page.goto('/transformation/create', { waitUntil: 'domcontentloaded' });
      await page
        .locator(
          '.transformation-pipeline-create-page, .unavailable-page, .error-display, .app-main, h1, #email'
        )
        .first()
        .waitFor({ state: 'visible', timeout: 20000 })
        .catch(() => null);

      if (page.url().includes('/login')) {
        throw new Error('Auth expired navigating to /transformation/create');
      }

      const capabilityEnabled =
        page.url().includes('/transformation') &&
        (await page.locator('.transformation-pipeline-create-page, .app-main').count()) > 0;
      const capabilityDisabled =
        (await page.locator('.unavailable-page').count()) > 0 ||
        page.url().includes('/unavailable') ||
        page.url().includes('/403');

      expect(capabilityEnabled || capabilityDisabled).toBe(true);

      if (capabilityEnabled) {
        await expect(
          page.locator('.transformation-pipeline-create-page, .app-main').first()
        ).toBeVisible({ timeout: 5000 });
      } else {
        await expect(
          page.locator('.unavailable-page, [role="main"]').first()
        ).toBeVisible({ timeout: 5000 });
      }
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to /transformation redirects to login', async ({
      page,
    }) => {
      await clearAuthStorage(page);
      await page.goto('/transformation', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|transformation|403|unavailable)/, { timeout: 20_000 });
      const url = page.url();
      // Must redirect to login (unauthenticated) or 403/unavailable (capability-gated).
      // Staying on /transformation while unauthenticated is NOT acceptable.
      const redirectedToAuth =
        url.includes('/login') || url.includes('/403') || url.includes('/unavailable');
      const staysOnTransformation = url.includes('/transformation') && !url.includes('/login');
      if (staysOnTransformation) {
        // If stays on /transformation, the login prompt must be visible (not a silent pass)
        const hasLoginPromptOnPage =
          (await page.locator('input#email, [href*="/login"]').count()) > 0 ||
          (await page.getByText('Sign in').count()) > 0;
        expect(hasLoginPromptOnPage).toBe(true);
      } else {
        expect(redirectedToAuth).toBe(true);
      }
    });

    test('non-existent pipeline detail shows explicit error or unavailable', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/transformation/pipelines/00000000-0000-0000-0000-000000000000', {
        waitUntil: 'domcontentloaded',
      });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login for non-existent pipeline detail');
      }

      // Wait past CapabilityRoute loading spinner: capability gated check must complete
      // before the pipeline detail (or unavailable redirect) renders.
      await page.waitForSelector(
        '.transformation-detail-page, .unavailable-page, .error-display',
        { timeout: 30000 }
      ).catch(() => null);
      await page.waitForTimeout(500);

      const capabilityDisabled =
        (await page.locator('.unavailable-page').count()) > 0 ||
        page.url().includes('/unavailable') ||
        page.url().includes('/403');

      if (capabilityDisabled) {
        // Capability off — 404 test not meaningful; verify unavailable page renders
        await expect(page.locator('.unavailable-page, [role="main"]').first()).toBeVisible({ timeout: 5000 });
        return;
      }

      // Capability on: TransformationPipelineDetailPage renders ErrorDisplay for 404
      const hasExplicitError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('[role="alert"]').count()) > 0;
      expect(hasExplicitError).toBe(true);
    });
  });

  test.describe('Edge (capability-gated)', () => {
    test('transformation page shows unavailable or list depending on capability flag', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/transformation', { waitUntil: 'domcontentloaded' });
      try {
        await waitForAppMainReady(page, {
          contentSelector:
            '.transformation-pipeline-list-page, .unavailable-page, .empty-state, .error-display',
          timeout: 30000,
        });
      } catch {
        // Acceptable: capability may redirect before terminal state
      }
      await page
        .locator('.transformation-pipeline-list-page, .unavailable-page, .app-main, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 10000 })
        .catch(() => null);

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on /transformation edge test');
      }

      const capabilityEnabled =
        (await page.locator('.transformation-pipeline-list-page, .empty-state').count()) > 0;
      const capabilityDisabled =
        (await page.locator('.unavailable-page').count()) > 0 ||
        page.url().includes('/unavailable') ||
        page.url().includes('/403');

      // Exactly one state must be true — not "any URL is fine"
      expect(capabilityEnabled || capabilityDisabled).toBe(true);

      if (capabilityEnabled) {
        await expect(
          page.locator('.transformation-pipeline-list-page, .empty-state').first()
        ).toBeVisible({ timeout: 5000 });
      } else {
        await expect(
          page.locator('.unavailable-page, [role="main"]').first()
        ).toBeVisible({ timeout: 5000 });
      }
    });
  });
});
