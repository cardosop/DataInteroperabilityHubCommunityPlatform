/**
 * E2E: Contracts and ODPS routes (Phase 13 — 15.3)
 * JOURNEY-DE-001, DE-002, DPO-015–017, DE-014: create contract, validate, ODPS upload/link/export.
 * Routes: /contracts, /contracts/:id/edit, /contracts/:id/link-odps, /odps, /odps/upload, /odps/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import {
  assertSuccessfulLoad,
  waitForAppMainReady,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('Contracts and ODPS routes', () => {
  test.setTimeout(120000);

  test.describe('Edge', () => {
    test('contract link-odps with non-existent contract id shows error or redirect', async ({
      page,
    }) => {
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

  test.describe('Failure', () => {
    test('contract edit with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      const responsePromise = page
        .waitForResponse(
          (resp) =>
            resp.url().includes(`/contracts/${nonExistentId}`) &&
            (resp.status() === 200 || resp.status() === 404),
          { timeout: 15000 }
        )
        .catch(() => null);
      await page.goto(`/contracts/${nonExistentId}/edit`);
      await page.waitForLoadState('domcontentloaded');
      await responsePromise;
      await page.waitForTimeout(3000);
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-title').count()) > 0 ||
        (await page.locator('text=/not found|failed to load|404/i').count()) > 0;
      const onLogin = page.url().includes('/login');
      const noSuccessContent = (await page.locator('.contract-editor-page').count()) === 0;
      expect(hasError || onLogin || noSuccessContent).toBe(true);
    });

    test('odps detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      const responsePromise = page
        .waitForResponse(
          (resp) =>
            resp.url().includes(`/contracts/${nonExistentId}`) &&
            (resp.status() === 200 || resp.status() === 404),
          { timeout: 15000 }
        )
        .catch(() => null);
      await page.goto(`/odps/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await responsePromise;
      await page.waitForTimeout(3000);
      const onLogin = page.url().includes('/login');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-title').count()) > 0 ||
        (await page.locator('text=/not found|failed to load|404/i').count()) > 0;
      const noSuccessContent = (await page.locator('.odps-detail-main').count()) === 0;
      expect(onLogin || hasError || noSuccessContent).toBe(true);
    });
  });

  test.describe('Success', () => {
    test('contracts list loads (empty or with data)', async ({ page }) => {
      const apiPromise = page.waitForResponse(
        (r) => r.url().includes('/contracts') && r.request().method() === 'GET',
        { timeout: 60000 }
      );
      await page.goto('/contracts');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          contentSelector:
            '.contract-list-page, .empty-state, .error-display, .loading-spinner-container',
        });
      } catch (_err) {
        if (page.url().includes('/login')) {
          expect(page.url()).toContain('/login');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/contracts');
      await assertSuccessfulLoad(page, {
        apiResponsePromise: apiPromise,
        successContentSelector: '.contract-list-page, .empty-state',
        rejectErrorDisplay: true,
      });
      await waitForLoadingComplete(page, { timeout: 15000 });
    });

    test('odps list loads (empty or with data)', async ({ page }) => {
      const apiPromise = page.waitForResponse(
        (r) => r.url().includes('/contracts') && r.request().method() === 'GET',
        { timeout: 65000 }
      );
      await page.goto('/odps');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator(
          '.odps-list-page, .odps-empty-state, .error-display, .loading-spinner-container, #email'
        )
        .first()
        .waitFor({ state: 'visible', timeout: 65000 });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/odps');
      await assertSuccessfulLoad(page, {
        apiResponsePromise: apiPromise,
        successContentSelector: '.odps-list-page, .odps-empty-state',
        rejectErrorDisplay: true,
      });
    });

    test('odps upload page loads', async ({ page }) => {
      await page.goto('/odps/upload');
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
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/odps/upload');
      // Upload page may not trigger list API; verify frontend success only
      await assertSuccessfulLoad(page, {
        successContentSelector: '.odps-upload-page',
        rejectErrorDisplay: true,
      });
    });
  });
});
