/**
 * E2E: UC-CM-002 — Validate Contract / Link ODPS
 *
 * Use Case: Validate Contract, Link ODPS to Contract
 * Persona: Data Product Owner, Data Engineer
 * Reference: docs/USE_CASES.md, docs/TEST_TRACEABILITY.md
 *
 * Success/Failure/Edge. Routes: /contracts/:id/edit, /contracts/:id/link-odps.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { createODCSContractViaApi } from '../../fixtures/api-assets';
import { getTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('UC-CM-002: Validate Contract / Link ODPS', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('contract edit page loads when contract exists', async ({ page }) => {
      const user = await getTestUser();
      const contractId = await createODCSContractViaApi(user);
      await loginAndNavigateToRoute(page, user, `/contracts/${contractId}`, {
        timeout: 60000,
        contentSelector: '.contract-detail-page, .contract-detail-content, .error-display',
        acceptRedirectToLogin: false,
      });
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on contract detail');
      }
      const editBtn = page.locator('button:has-text("Edit")');
      await expect(editBtn.first()).toBeVisible({ timeout: 15000 });
      await editBtn.first().click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.contract-editor-page, .error-display', { timeout: 15000 });
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login after opening contract edit');
      }
      expect(page.url()).toContain('/edit');
    });
  });

  test.describe('Failure', () => {
    test('contract edit with non-existent id shows error', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/contracts/00000000-0000-0000-0000-000000000000/edit', {
        timeout: 60000,
        contentSelector: '.contract-editor-page, .contract-detail-page, .error-display, [role="alert"]',
        acceptRedirectToLogin: false,
      });
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.contract-editor-page, .contract-detail-page',
        waitAfterLoad: 8000,
        selectorTimeout: 60000,
      });
    });
  });

  test.describe('Edge', () => {
    test('link-odps route with non-existent id shows error or redirect', async ({ page }) => {
      const user = await getTestUser();
      // ODPSLinkPage now renders ErrorDisplay BEFORE loading spinner when contract not found.
      // Do NOT include  — it would stop waitForAppMainReady too early.
      await loginAndNavigateToRoute(page, user, '/contracts/00000000-0000-0000-0000-000000000000/link-odps', {
        timeout: 60000,
        contentSelector: '.error-display, [role="alert"], .odps-link-page',
        acceptRedirectToLogin: false,
      });
      const url = page.url();
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('[role="alert"]').count()) > 0;
      expect(url.includes('/login') || url.includes('/403') || hasError).toBe(true);
    });
  });
});
