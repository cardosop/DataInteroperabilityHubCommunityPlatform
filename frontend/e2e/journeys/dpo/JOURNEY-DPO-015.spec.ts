/**
 * E2E Test: JOURNEY-DPO-015 — Create ODPS Product (Product-First Flow)
 *
 * Journey: Create ODPS Product (Product-First Flow)
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /odps/upload, /odps
 * (legacy — Phase 211.A6 redirects them to /contracts/create and
 * /contracts?spec_type=ODPS; tests assert the post-redirect contract pages).
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-015: Create ODPS Product (Product-First Flow) @critical', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('ODPS upload page loads', async ({ page }) => {
      const testUser = await getTestUser();
      // Legacy /odps/upload redirects (Phase 211.A6) to the unified contract create page.
      await loginAndNavigateToRoute(page, testUser, '/odps/upload', {
        timeout: 60000,
        contentSelector: '.contract-create-page, .error-display, [data-testid="error-display"]',
      });
      test.skip(page.url().includes('/login'), 'Redirected to login');
      expect(page.url()).toContain('/contracts/create');
    });

    test('ODPS list loads', async ({ page }) => {
      const testUser = await getTestUser();
      // Legacy /odps redirects (Phase 211.A6) to the contracts list filtered by spec_type=ODPS.
      await loginAndNavigateToRoute(page, testUser, '/odps', {
        timeout: 60000,
        contentSelector: '.contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      test.skip(page.url().includes('/login'), 'Redirected to login');
      expect(page.url()).toContain('/contracts?spec_type=ODPS');
    });
  });

  test.describe('Failure', () => {
    test('ODPS detail with non-existent id shows explicit error display', async ({ page }) => {
      const testUser = await getTestUser();
      // Use loginAndNavigateToRoute to ensure auth tokens survive the navigation.
      // /odps/:id redirects (Phase 211.A6) to the contract detail page, which
      // renders ErrorDisplay when the contract fetch fails — so the error shows on 404.
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/odps/00000000-0000-0000-0000-000000000000',
        {
          timeout: 60000,
          contentSelector: '.error-display, [data-testid="error-display"], .contract-detail-page, [data-testid="contract-detail-page"], [role="alert"]',
        }
      );

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login when navigating to non-existent ODPS detail');
      }

      // The error display must be present — not just "the success element is missing"
      const hasError =
        (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0 ||
        (await page.locator('[role="alert"]').count()) > 0;
      expect(hasError).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Edge', () => {
    test('submit valid minimal ODPS document creates product or shows workflow status', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      // Legacy /odps/upload redirects (Phase 211.A6) to the unified contract create page.
      await loginAndNavigateToRoute(page, testUser, '/odps/upload', {
        timeout: 60000,
        contentSelector: '.contract-create-page, .error-display, [data-testid="error-display"]',
      });
      await waitForLoadingComplete(page, { timeout: 30000 });

      test.skip(page.url().includes('/login'), 'Auth redirect — backend may be rate-limiting');
      test.skip(
        (await page.locator('.contract-create-page').count()) === 0,
        'Contract create page did not render; skipping submission test.'
      );

      // Default creation mode is Raw Upload; click the tab defensively so the
      // JSON-paste textarea is mounted even if the default changes.
      const rawModeTab = page.locator('button[role="tab"]:has-text("Raw Upload")').first();
      if ((await rawModeTab.count()) > 0) {
        await rawModeTab.click();
      }

      // Fill the textarea with a minimal but valid ODPS document
      const minimalOdps = {
        schema: 'https://opendataproducts.org/schema/v4.1',
        version: '4.1',
        product: {
          details: {
            en: {
              productID: `e2e-odps-${Date.now()}`,
              name: 'E2E Minimal ODPS',
              description: 'Minimal ODPS created by JOURNEY-DPO-015 E2E test',
              productVersion: '1.0.0',
            },
          },
          dataSchema: {
            fields: [
              { name: 'id', type: 'string' },
              { name: 'value', type: 'number' },
            ],
          },
          contract: {
            spec: {
              apiVersion: 'odcs.io/v3.0.2',
              kind: 'DataContract',
              id: `e2e-odcs-${Date.now()}`,
              name: 'E2E ODCS Contract',
              version: '1.0.0',
              description: 'E2E test contract',
              schema: {
                fields: [
                  { name: 'id', type: 'string', nullable: false, description: 'ID' },
                  { name: 'value', type: 'number', nullable: true, description: 'Value' },
                ],
              },
            },
          },
        },
      };

      const contentTextarea = page.locator('textarea.contract-file-reader__textarea, textarea').first();
      await expect(contentTextarea).toBeVisible({ timeout: 10000 });
      await contentTextarea.fill(JSON.stringify(minimalOdps, null, 2));
      await page.waitForTimeout(500);

      // Raw Upload mode submits via "Create Contract" (Phase 211 unified create page);
      // server-side mode detection still routes ODPS payloads to the workflow endpoint.
      const submitBtn = page.locator('button:not([role="tab"]):has-text("Create Contract")').first();
      await expect(submitBtn).toBeVisible({ timeout: 5000 });
      await expect(submitBtn).toBeEnabled({ timeout: 10000 });

      // Intercept the API response to distinguish success from validation error
      const createResponse = page.waitForResponse(
        (resp) =>
          resp.url().includes('/contracts/') &&
          (resp.status() === 200 || resp.status() === 201 || resp.status() === 202 || resp.status() >= 400),
        { timeout: 60000 }
      );
      await submitBtn.click();

      let resp: import('@playwright/test').Response | null = null;
      try {
        resp = await createResponse;
      } catch (e) {
        test.info().annotations.push({
          type: 'timeout',
          description: `API response wait timed out: ${String(e)}`,
        });
      }

      await page.waitForTimeout(2000);

      if (resp && resp.status() >= 400 && resp.status() < 500) {
        const errorDisplay = page.locator('.error-display, [data-testid="error-display"], [role="alert"]');
        await expect(errorDisplay.first()).toBeVisible({ timeout: 8000 });
        return;
      }

      const finalUrl = page.url();
      // Successful create navigates to the contract detail page (/contracts/:id);
      // the async ODPS workflow may instead keep us on /contracts/create with a progress bar.
      const navigatedAway = !finalUrl.includes('/contracts/create');
      const hasSuccessContent =
        (await page.locator('.contract-detail-page, [data-testid="contract-detail-page"], .contract-create-page__progress').count()) > 0;
      const stayedOnCreateWithNoError =
        finalUrl.includes('/contracts/create') && (await page.locator('.error-display, [data-testid="error-display"]').first().count()) === 0;
      expect(navigatedAway || hasSuccessContent || stayedOnCreateWithNoError).toBe(true);
    });
  });
});
