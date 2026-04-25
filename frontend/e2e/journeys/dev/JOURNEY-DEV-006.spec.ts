/**
 * E2E Test: JOURNEY-DEV-006 — Integrate Transformation Pipeline API
 *
 * Journey: Integrate Transformation Pipeline API
 * Persona: External Developer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Verifies that the transformation API documentation/integration page is accessible.
 * The transformation pipeline feature is capability-gated (`transformation` capability).
 *
 * Status: IMPLEMENTED (Phase 115A) — all tests run against the real backend.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DEV-006: Integrate Transformation Pipeline API', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('transformation page loads for API integration (list or unavailable)', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/transformation', {
        timeout: 60000,
        contentSelector:
          '.transformation-pipeline-list-page, .unavailable-page, .empty-state, .error-display',
      });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on /transformation');
      }

      // intentional: probes optional UI presence via selector — same shape as waitFor; absence is a legitimate state handled by the branch below.
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
  });

  test.describe('Failure', () => {
    test('unauthenticated access to /transformation redirects to login', async ({
      page,
    }) => {
      await clearAuthStorage(page);
      await page.goto('/transformation', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|transformation|403|unavailable)/, { timeout: 20_000 });
      const url = page.url();
      const redirectedToAuth =
        url.includes('/login') || url.includes('/403') || url.includes('/unavailable');
      const staysOnTransformation = url.includes('/transformation') && !url.includes('/login');
      if (staysOnTransformation) {
        const hasLoginPromptOnPage =
          (await page.locator('input#email, [href*="/login"]').count()) > 0 ||
          (await page.getByText('Sign in').count()) > 0;
        expect(hasLoginPromptOnPage).toBe(true);
      } else {
        expect(redirectedToAuth).toBe(true);
      }
    });
  });
});
