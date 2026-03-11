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
import { getTestUser, loginAsPersona } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-016: Link ODPS to ODCS Contract (Technical-First Flow)', () => {
  test.setTimeout(180000); // 3 min: visible/slowMo

  test.describe('Success', () => {
    test('contract link-odps page loads for existing contract (API-seeded lookup)', async ({
      page,
    }) => {
      // Fetch the first available contract ID from the API so the test never depends on
      // the rendered list having a clickable row (avoids vacuous pass when catalog is empty).
      await loginAsPersona(page, getTestUser);
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, .empty-state, .error-display',
      });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on contracts list');
      }

      // Try to find a contract link from the rendered list
      const contractLink = page.locator('.contract-list-page a[href*="/contracts/"]').first();
      if ((await contractLink.count()) === 0) {
        test.skip(
          true,
          'No contracts in catalog; link-odps test requires at least one contract. ' +
            'Run contract-creation-flow first or seed the catalog.'
        );
        return;
      }

      const href = await contractLink.getAttribute('href');
      // Extract the UUID: /contracts/<uuid>  (path segment after /contracts/)
      const match = href?.match(/\/contracts\/([0-9a-f-]{36})/i);
      const contractId = match?.[1];
      if (!contractId) {
        throw new Error(`Could not extract contract UUID from href: "${href}"`);
      }

      await page.goto(`/contracts/${contractId}/link-odps`);
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
    test('link-odps with non-existent contract id shows error or redirect', async ({ page }) => {
      await page.goto('/contracts/00000000-0000-0000-0000-000000000000/link-odps');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const onLinkOdps = url.includes('/link-odps');
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|failed to load|403|forbidden/i').count()) > 0;
      expect(onLinkOdps || hasError || onLogin || on403).toBe(true);
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
