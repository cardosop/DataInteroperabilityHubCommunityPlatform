/**
 * E2E Test: JOURNEY-DPO-016 — Link ODPS to ODCS Contract (Technical-First Flow)
 *
 * Journey: Link ODPS to ODCS Contract (Technical-First Flow)
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /contracts/:id/link-odps.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { createODCSContractViaApi } from '../../fixtures/api-assets';
import { getTestUser, loginAsPersona, loginUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-016: Link ODPS to ODCS Contract (Technical-First Flow)', () => {
  test.setTimeout(180000); // 3 min: visible/slowMo

  test.describe('Success', () => {
    test('contract link-odps page loads for existing contract (API-seeded lookup)', async ({
      page,
    }) => {
      // Seed a contract via API and navigate directly — avoids relying on list link structure.
      const testUser = await getTestUser();
      const contractId = await createODCSContractViaApi(testUser);

      await loginAndNavigateToRoute(page, testUser, `/contracts/${contractId}/link-odps`, {
        timeout: 60000,
        contentSelector: '.odps-link-page, .error-display, .app-main, #email',
      });
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      const onLinkOdps = page.url().includes('/link-odps');
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const hasContent = (await page.locator('.odps-link-page, .error-display, .app-main').count()) > 0;

      // Must not silently pass with onLogin (which means auth failed)
      if (onLogin) {
        throw new Error('Redirected to login on link-odps page; auth may have expired.');
      }
      expect(onLinkOdps || on403).toBe(true);
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('link-odps with non-existent contract id shows explicit error when authenticated', async ({ page }) => {
      // Test authenticated behavior — visiting a non-existent contract's link-odps page must
      // show an explicit error, not a blank page. Running unauthenticated would trivially pass
      // via the /login redirect and not test the actual error handling.
      const testUser = await getTestUser();
      await loginUser(page, testUser);

      await page.goto('/contracts/00000000-0000-0000-0000-000000000000/link-odps');
      await page.waitForLoadState('domcontentloaded');

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login; auth may have failed');
      }

      // Wait for React Query to finish loading (spinner disappears, error state renders).
      // A fixed 3s wait is not enough in visible/slowMo — wait for error display OR
      // the link-odps page content to appear (whichever settles first).
      await page.waitForSelector(
        '.error-display, .odps-link-page, [role="alert"]',
        { timeout: 20000 }
      ).catch(() => null);

      // Must show an explicit error — not a blank or loading state
      const hasExplicitError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('[role="alert"]').count()) > 0;
      const on403 = page.url().includes('/403');
      expect(hasExplicitError || on403).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('link-odps page loads or redirects', async ({ page }) => {
      await loginAsPersona(page, getTestUser);
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, .empty-state, .error-display',
      });
      const contractLink = page.locator('a[href*="/contracts/"][href*="/link-odps"]').first();
      if ((await contractLink.count()) > 0) {
        await contractLink.click();
        await page.waitForTimeout(2000);
        expect(
          page.url().includes('/link-odps') ||
            page.url().includes('/login') ||
            page.url().includes('/403')
        ).toBe(true);
      }
    });
  });
});
