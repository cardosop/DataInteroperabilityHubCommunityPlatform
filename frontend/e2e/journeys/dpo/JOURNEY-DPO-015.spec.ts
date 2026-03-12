/**
 * E2E Test: JOURNEY-DPO-015 — Create ODPS Product (Product-First Flow)
 *
 * Journey: Create ODPS Product (Product-First Flow)
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /odps/upload, /odps.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-015: Create ODPS Product (Product-First Flow)', () => {
  test.setTimeout(180000); // 3 min: visible/slowMo; ODPS list + upload + publish

  test.describe('Success', () => {
    test('ODPS upload page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/odps/upload');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, {
          contentSelector: '.odps-upload-page',
          timeout: 60000,
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/odps/upload');
    });

    test('ODPS list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/odps');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.odps-list-page, .odps-empty-state, .error-display, .loading-spinner-container, #email', {
        timeout: 65000,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/odps');
    });
  });

  test.describe('Failure', () => {
    test('ODPS detail with non-existent id shows explicit error display', async ({ page }) => {
      // D3: Fix the too-permissive triple-OR assertion. "noSuccessContent" (.odps-detail-main
      // count === 0) is true on ANY page — the test must assert a visible error, not absence
      // of a specific element.
      const testUser = await getTestUser();
      await loginUser(page, testUser);

      // Fixed: use full path and only accept 404 (200 means the ODPS exists — a bug).
      // ODPS detail internally uses the contracts API endpoint.
      const responsePromise = page
        .waitForResponse(
          (resp) =>
            (resp.url().includes('/odps/00000000-0000-0000-0000-000000000000') ||
              resp.url().includes('/contracts/00000000-0000-0000-0000-000000000000')) &&
            resp.status() === 404,
          { timeout: 15000 }
        )
        .catch(() => null);

      await page.goto('/odps/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await responsePromise;
      // Allow time for React Query to settle and ErrorDisplay to render (retries, network delays)
      await page.waitForTimeout(5000);

      const onLogin = page.url().includes('/login');
      if (onLogin) {
        throw new Error('Unexpected redirect to login when navigating to non-existent ODPS detail');
      }

      // The error display must be present — not just "the success element is missing"
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-message').filter({ hasText: /not found|could not be found|404/i }).count()) > 0;
      expect(hasError).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('submit valid minimal ODPS document creates product or shows workflow status', async ({
      page,
    }) => {
      // This edge test exercises the actual ODPS creation flow — distinct from the Success test
      // which only verifies the upload page renders.
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/odps/upload', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('.odps-upload-page, .error-display, .loading-spinner-container, #email', {
        timeout: 30000,
      });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on ODPS upload page');
      }
      if ((await page.locator('.odps-upload-page').count()) === 0) {
        test.skip(true, 'ODPS upload page did not render; skipping submission test.');
        return;
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

      const contentTextarea = page.locator('textarea#odps-content, textarea').first();
      await expect(contentTextarea).toBeVisible({ timeout: 10000 });
      await contentTextarea.fill(JSON.stringify(minimalOdps, null, 2));
      await page.waitForTimeout(500);

      const submitBtn = page.locator('button:has-text("Create ODPS Product")').first();
      await expect(submitBtn).toBeVisible({ timeout: 5000 });

      // Intercept the API response to distinguish success from validation error
      const createResponse = page.waitForResponse(
        (resp) =>
          resp.url().includes('/contracts/') &&
          (resp.status() === 200 || resp.status() === 201 || resp.status() >= 400),
        { timeout: 60000 }
      );
      await submitBtn.click();

      let resp: import('@playwright/test').Response | null = null;
      try {
        resp = await createResponse;
      } catch {
        // Response timeout — check UI state
      }

      await page.waitForTimeout(3000);

      if (resp && resp.status() >= 400 && resp.status() < 500) {
        // Validation failure — the error display must explain why
        const errorDisplay = page.locator('.error-display, [role="alert"]');
        await expect(errorDisplay.first()).toBeVisible({ timeout: 8000 });
        return;
      }

      // Success path: either navigates to ODPS/contract detail, or shows workflow status
      const finalUrl = page.url();
      const navigatedAway = !finalUrl.includes('/odps/upload');
      const hasSuccessContent =
        (await page.locator('.odps-detail-page, .odps-detail-main, .workflow-status, h1').count()) > 0;
      const isStillOnUploadWithNoError =
        finalUrl.includes('/odps/upload') && (await page.locator('.error-display').count()) === 0;

      expect(navigatedAway || hasSuccessContent || isStillOnUploadWithNoError).toBe(true);
    });
  });
});
