/**
 * E2E Test: JOURNEY-AUD-005 — Audit Transformation Pipelines
 *
 * Journey: Audit Transformation Pipelines
 * Persona: Auditor
 * Reference: docs/USER_JOURNEYS.md
 *
 * The audit page shows transformation event types when the transformation capability
 * is enabled. When disabled, the page still loads (audit is always available).
 * The transformation filter may or may not be present depending on capability.
 *
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import { assertListPageLoads, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-AUD-005: Audit Transformation Pipelines', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('audit page loads with transformation event types or empty state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/audit', {
        timeout: 60000,
        contentSelector: '.audit-event-list-page, .empty-state, .unavailable-page, .error-display',
      });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on /audit');
      }

      // Accept /403 for role-gated access
      if (page.url().includes('/403')) {
        test.skip(true, 'User lacks audit role on this environment');
        return;
      }

      await assertListPageLoads(page, '.audit-event-list-page, .empty-state, .unavailable-page', {
        timeout: 60000,
      });

      // Check if transformation event type filter is available
      const transformationFilter = page.locator(
        'option:has-text("Transformation"), [data-testid="event-type-filter"] option[value*="transform" i], button:has-text("Transformation")'
      );
      const hasTransformationFilter = (await transformationFilter.count()) > 0;
      test.info().annotations.push({
        type: 'transformation-filter',
        description: hasTransformationFilter
          ? 'Transformation event type filter is available'
          : 'Transformation event type filter not found — capability may be disabled',
      });
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to /audit redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/audit', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|audit|403|unavailable)/, { timeout: 20_000 });
      const url = page.url();
      const redirectedToAuth =
        url.includes('/login') || url.includes('/403') || url.includes('/unavailable');
      if (url.includes('/audit') && !url.includes('/login')) {
        // Stayed on /audit without auth — check for login prompt on page
        const hasLoginPromptOnPage =
          (await page.locator('input#email, [href*="/login"]').count()) > 0 ||
          (await page.getByText('Sign in').count()) > 0;
        expect(
          hasLoginPromptOnPage,
          'If staying on /audit unauthenticated, must show login prompt'
        ).toBe(true);
      } else {
        expect(redirectedToAuth, 'Expected redirect to login or 403').toBe(true);
      }
    });
  });

  test.describe('Edge', () => {
    test('audit page renders without 500 errors regardless of capabilities', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/audit', {
        timeout: 60000,
        contentSelector: '.audit-event-list-page, .empty-state, .unavailable-page, .error-display',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        // Auth/role redirect — acceptable edge case
        return;
      }
      // Must not have 500 server errors
      const has500 = (await page.locator('text=/500|internal server error/i').count()) > 0;
      expect(has500, 'Audit page must not show 500 errors').toBe(false);
      // Must render meaningful content
      const hasContent =
        (await page.locator('.audit-event-list-page, .empty-state, .unavailable-page').count()) > 0;
      expect(hasContent, 'Expected audit content, empty state, or unavailable page').toBe(true);
    });
  });
});
