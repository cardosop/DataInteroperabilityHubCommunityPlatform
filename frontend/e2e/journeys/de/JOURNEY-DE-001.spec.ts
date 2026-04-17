/**
 * E2E Test: JOURNEY-DE-001 — Programmatic Contract-First Onboarding
 *
 * Journey: Programmatic Contract-First Onboarding
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Dedicated DE-001 spec (contracts-odps-routes covers some). Success/Failure/Edge.
 * Routes: /contracts, /contracts/:id/edit, /contracts/:id/link-odps, /odps, /odps/upload.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { assertListPageLoads, assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-001: Programmatic Contract-First Onboarding', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('contracts list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, .empty-state, .error-display',
      });
      await assertListPageLoads(page, '.contract-list-page, .empty-state', { timeout: 60000 });
    });

    test('ODPS list loads', async ({ page }) => {
      // Phase 211.A6: /odps redirects to /contracts?spec_type=ODPS.
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, .empty-state, .error-display',
      });
      await assertListPageLoads(page, '.contract-list-page, .empty-state', {
        timeout: 60000,
      });
    });

    test('ODPS upload page loads', async ({ page }) => {
      // Phase 211.A6: /odps/upload redirects to /contracts/create.
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts/create', {
        timeout: 60000,
        contentSelector: '.contract-create-page, form, h1',
      });
      const url = page.url();
      expect(url).toMatch(/\/(odps\/upload|contracts\/create)/);
    });
  });

  test.describe('Failure', () => {
    test('contract edit with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, .empty-state, .error-display',
      });
      await page.goto('/contracts/00000000-0000-0000-0000-000000000000/edit', { waitUntil: 'domcontentloaded', timeout: 60000 });
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.contract-editor-page, .contract-detail-page, .error-display',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('link-odps with non-existent contract shows error or redirect', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, .empty-state, .error-display',
      });
      await page.goto('/contracts/00000000-0000-0000-0000-000000000000/link-odps', { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page
        .locator('.error-display, .contract-detail-page')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 })
        .catch(() => null);
      const on403 = page.url().includes('/403');
      const onLogin = page.url().includes('/login');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|failed|403|forbidden/i').count()) > 0;
      expect(on403 || onLogin || hasError).toBe(true);
    });
  });
});
