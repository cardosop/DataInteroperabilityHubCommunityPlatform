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
import { clearAuthStorage, getAuditorUser } from '../../fixtures/auth';
import { assertListPageLoads, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-AUD-005: Audit Transformation Pipelines', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('audit page loads with transformation event types or empty state', async ({ page }) => {
      // The journey's named persona is Auditor; using getTestUser (DPO) here
      // was a workaround that masked a real role-assignment problem behind a
      // graceful test.skip on /403. Using the auditor persona aligns the test
      // with the journey's documented persona — and if the auditor account
      // does NOT have the audit role on staging, that's a real environment
      // misconfiguration we want to surface, not paper over.
      const auditorUser = await getAuditorUser();
      await loginAndNavigateToRoute(page, auditorUser, '/audit', {
        timeout: 60000,
        contentSelector: '.audit-event-list-page, [data-testid="audit-event-list-page"], .empty-state, [data-testid="empty-state"], .unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"]',
      });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on /audit');
      }

      // /403 from the AUDITOR persona on /audit is a real env issue (role not
      // assigned by ensure_e2e_user_roles), NOT an acceptable terminal state
      // for this journey. Fail loud so it gets fixed at the env level instead
      // of decaying into a permanent green-skip.
      if (page.url().includes('/403')) {
        throw new Error(
          'Auditor user got /403 on /audit. The auditor role is not assigned ' +
            'on this environment. Fix: run `python manage.py ensure_e2e_user_roles` ' +
            'on the staging API pod, or pre-seed the auditor account in the deploy step.'
        );
      }

      await assertListPageLoads(page, '.audit-event-list-page, [data-testid="audit-event-list-page"], .empty-state, [data-testid="empty-state"], .unavailable-page, [data-testid="unavailable-page"]', {
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
      // Match the Success persona: auditor is the journey's documented role,
      // and the edge assertion (no 500s) is independent of the user identity.
      const auditorUser = await getAuditorUser();
      await loginAndNavigateToRoute(page, auditorUser, '/audit', {
        timeout: 60000,
        contentSelector: '.audit-event-list-page, [data-testid="audit-event-list-page"], .empty-state, [data-testid="empty-state"], .unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"]',
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
        (await page.locator('.audit-event-list-page, [data-testid="audit-event-list-page"], .empty-state, [data-testid="empty-state"], .unavailable-page, [data-testid="unavailable-page"]').count()) > 0;
      expect(hasContent, 'Expected audit content, empty state, or unavailable page').toBe(true);
    });
  });
});
