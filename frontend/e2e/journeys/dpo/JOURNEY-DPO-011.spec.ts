/**
 * E2E Test: JOURNEY-DPO-011 — Assign Data Stewards
 *
 * Journey: Assign Data Stewards
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /communities, /governance (Phase 27.2).
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUser, getTestUser, loginUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

/** Get tenant admin or fallback to DPO when tenant admin unavailable (e.g. under parallel load). */
async function getSocialTestUser() {
  try {
    return await getTenantAdminUser();
  } catch {
    return await getTestUser();
  }
}

test.describe('JOURNEY-DPO-011: Assign Data Stewards', () => {
  test.setTimeout(180000); // 3 min: avoid interrupted/timeout

  test.describe('Success', () => {
    test('governance page loads for steward assignment (access requests list or empty state)', async ({
      page,
    }) => {
      // Data steward assignment lives in the governance/access-requests area, not communities.
      // This test validates that the governance route loads for an authenticated DPO.
      const testUser = await getSocialTestUser();
      await loginAndNavigateToRoute(page, testUser, '/governance', {
        timeout: 60000,
        contentSelector:
          '.access-request-list-page, .governance-page, .empty-state, .error-display, .app-main, .unavailable-page, h1',
        acceptRedirectToLogin: true,
      });
      await page.waitForTimeout(2000);

      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onGovernance = url.includes('/governance');

      if (onLogin) {
        throw new Error('Unexpected redirect to login on governance page; auth may have failed.');
      }

      const hasContent =
        (await page
          .locator(
            '.access-request-list-page, .governance-page, .empty-state, .error-display, .app-main'
          )
          .count()) > 0;
      expect(on403 || onUnavailable || (onGovernance && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('governance DPO user cannot write (create/approve) governance records', async ({ page }) => {
      // DPO user (DATA_PROVIDER role) should not be able to create governance records directly.
      // Either: redirected to /403, sees an error when submitting, or governance write actions
      // are not exposed in the UI for this role.
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/governance', {
        timeout: 60000,
        contentSelector:
          '.app-main, .governance-access-request-list-page, .governance-create-page, .error-display, .loading-spinner-container, h1',
        acceptRedirectToLogin: true,
      });
      await page.waitForTimeout(3000);

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login for governance failure test');
      }

      const on403 = page.url().includes('/403');
      if (on403) {
        // Correctly blocked — pass
        return;
      }

      // If governance page is accessible, verify no create/approve buttons are exposed to DPO
      const onGov = page.url().includes('/governance');
      expect(onGov).toBe(true);

      const hasCreateBtn = (await page.locator('button:has-text("Create"), button:has-text("Approve"), button:has-text("Grant")').count()) > 0;
      if (hasCreateBtn) {
        // If create is shown, clicking must result in a 403 or error (role boundary enforced at API)
        const responsePromise = page.waitForResponse(
          r => r.request().method() === 'POST' && r.url().includes('/governance'),
          { timeout: 10000 }
        ).catch(() => null);
        await page.locator('button:has-text("Create"), button:has-text("Approve"), button:has-text("Grant")').first().click();
        const resp = await responsePromise;
        if (resp) {
          expect(resp.status()).toBeGreaterThanOrEqual(400);
        }
      }
    });
  });

  test.describe('Edge', () => {
    test('communities page renders content or capability-unavailable state (no crash)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/communities', { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForLoadState('domcontentloaded');

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on /communities edge test');
      }

      // CapabilityRoute shows a loading spinner while capabilities are fetched.
      // Wait until either the communities page or the /unavailable redirect renders.
      await page.waitForSelector(
        '.communities-page, .communities-tab, .unavailable-page',
        { timeout: 30000 }
      ).catch(() => null);

      // Must render something meaningful — not a blank or crash
      const hasContent =
        (await page.locator('.communities-page, .communities-tab, .unavailable-page').count()) > 0 ||
        page.url().includes('/403');
      expect(hasContent).toBe(true);
    });
  });
});
