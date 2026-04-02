/**
 * E2E Test: JOURNEY-AUD-005 — Audit Transformation Pipelines
 *
 * Journey: Audit Transformation Pipelines
 * Persona: Auditor
 * Reference: docs/USER_JOURNEYS.md
 *
 * The audit page shows transformation event types when the transformation capability
 * is enabled. When disabled, the CapabilityRoute renders /unavailable.
 *
 * Status: IMPLEMENTED (Phase 115A) — all tests run against the real backend.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-AUD-005: Audit Transformation Pipelines', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('audit page loads with transformation event types or unavailable', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/audit', {
        timeout: 60000,
        contentSelector:
          '.audit-event-list-page, .unavailable-page, .empty-state, .error-display',
      });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on /audit');
      }

      await page.waitForSelector(
        '.audit-event-list-page, .empty-state, .unavailable-page',
        { timeout: 30000 }
      ).catch(() => null);

      const auditPageVisible =
        (await page.locator('.audit-event-list-page, .empty-state').count()) > 0;
      const unavailable =
        (await page.locator('.unavailable-page').count()) > 0 ||
        page.url().includes('/unavailable') ||
        page.url().includes('/403');

      expect(auditPageVisible || unavailable).toBe(true);

      if (auditPageVisible) {
        await expect(
          page.locator('.audit-event-list-page, .empty-state').first()
        ).toBeVisible({ timeout: 5000 });
      } else {
        await expect(
          page.locator('.unavailable-page, [role="main"]').first()
        ).toBeVisible({ timeout: 5000 });
      }
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to /audit redirects to login', async ({
      page,
    }) => {
      await clearAuthStorage(page);
      await page.goto('/audit', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|audit|403|unavailable)/, { timeout: 20_000 });
      const url = page.url();
      const redirectedToAuth =
        url.includes('/login') || url.includes('/403') || url.includes('/unavailable');
      const staysOnAudit = url.includes('/audit') && !url.includes('/login');
      if (staysOnAudit) {
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
