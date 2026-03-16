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
      // Wait for page to leave loading state: ODPSLinkPage shows a LoadingSpinner while
      // useContract + useODPSLinks are both pending (TanStack Query retries on 404 can take >3s).
      // Terminal states: error-display (contract not found), odps-link-page (success form), or login.
      await page
        .locator('.error-display, .odps-link-page, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 })
        .catch(() => null);
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-title').count()) > 0;

      // Redirect to login or 403 is always acceptable
      if (onLogin || on403) return;

      // If still on the link-odps path, the page must show an error boundary.
      // A nil contract ID should produce a 404/error, NOT a working form.
      // Previously, onLinkOdps (= url.includes('/link-odps')) was included in the OR —
      // but that was trivially always-true since we navigated there, making the assertion meaningless.
      const onLinkOdps = url.includes('/link-odps');
      if (onLinkOdps) {
        expect(hasError).toBe(true);
        return;
      }

      // Redirected to another route — fail with context if unexpected
      expect(url).toMatch(/\/(contracts|login|403)/);
    });
  });

  test.describe('Failure', () => {
    test('contract edit with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      // Only 404 is valid — 200 means the resource exists (backend bug).
      const responsePromise = page
        .waitForResponse(
          (resp) =>
            resp.url().includes(`/contracts/${nonExistentId}`) &&
            resp.status() === 404,
          { timeout: 15000 }
        )
        .catch(() => null);
      await page.goto(`/contracts/${nonExistentId}/edit`);
      await page.waitForLoadState('domcontentloaded');
      await responsePromise;

      // Race: wait for error or editor content rather than sleeping
      await page.locator('.error-display, .error-display-title, .contract-editor-page')
        .first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);

      const onLogin = page.url().includes('/login');
      if (onLogin) return;

      const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
      const hasNotFoundText = (await page.locator('.error-display-message').filter({ hasText: /not found|could not be found|404|matches the given query/i }).count()) > 0;
      if (hasErrorDisplay && !hasNotFoundText) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`Contract edit shows non-404 error for nil UUID: "${errText?.slice(0, 200)}". Expected "not found".`);
      }
      expect(hasErrorDisplay && hasNotFoundText).toBe(true);
    });

    test('odps detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      // ODPS products are stored as contracts internally. The ODPS detail page may call either
      // /api/v1/odps/{id}/ or /api/v1/contracts/{id}/. Watch for both to be robust against
      // future endpoint changes, and reject 200 (resource exists) as invalid.
      const responsePromise = page
        .waitForResponse(
          (resp) =>
            (resp.url().includes(`/odps/${nonExistentId}`) ||
              resp.url().includes(`/contracts/${nonExistentId}`)) &&
            resp.status() === 404,
          { timeout: 15000 }
        )
        .catch(() => null);
      await page.goto(`/odps/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await responsePromise;

      await page.locator('.error-display, .error-display-title, .odps-detail-page, .odps-detail-main')
        .first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);

      const onLogin = page.url().includes('/login');
      if (onLogin) return;

      const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
      const hasNotFoundText = (await page.locator('.error-display-message').filter({ hasText: /not found|could not be found|404|matches the given query/i }).count()) > 0;
      if (hasErrorDisplay && !hasNotFoundText) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`ODPS detail shows non-404 error for nil UUID: "${errText?.slice(0, 200)}". Expected "not found".`);
      }
      expect(hasErrorDisplay && hasNotFoundText).toBe(true);
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
      // ODPS internally uses /contracts endpoint OR a dedicated /odps endpoint depending on version
      const apiPromise = page.waitForResponse(
        (r) =>
          (r.url().includes('/contracts') || r.url().includes('/odps')) &&
          r.request().method() === 'GET',
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
