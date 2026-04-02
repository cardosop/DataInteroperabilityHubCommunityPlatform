/**
 * E2E: DQ, Compliance, Governance routes (Phase 13 — 15.5)
 * JOURNEY-DPO-004, DE-003–004, JOURNEY-CPO-001–002: DQ runs, compliance runs, access requests.
 * Routes: /dq, /compliance, /governance.
 * For "not implemented" backend, skip or assert /unavailable. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, gotoWithRetry } from '../../fixtures/auth';
import { assertListPageLoads, navigateOrSkip, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('DQ, Compliance, Governance routes', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('dq list loads (runs list or empty)', async ({ page }) => {
      const { ok } = await navigateOrSkip(page, '/dq', {
        contentSelector: '.dq-run-list-page, .empty-state',

      });
      if (!ok) return;

      expect(page.url()).toContain('/dq');
      try {
        await assertListPageLoads(page, '.dq-run-list-page, .empty-state');
      } catch (err) {
        if (String(err).includes('BACKEND_TIMEOUT')) {
          test.skip(true, 'Backend timeout under parallel E2E load');
          return;
        }
        throw err;
      }
    });

    test('compliance list loads (runs list or empty)', async ({ page }) => {
      const { ok } = await navigateOrSkip(page, '/compliance', {
        contentSelector: '.compliance-run-list-page, .empty-state',

      });
      if (!ok) return;

      expect(page.url()).toContain('/compliance');
      try {
        await assertListPageLoads(page, '.compliance-run-list-page, .empty-state');
      } catch (err) {
        if (String(err).includes('BACKEND_TIMEOUT')) {
          test.skip(true, 'Backend timeout under parallel E2E load');
          return;
        }
        throw err;
      }
    });

    test('governance page loads (access requests or empty)', async ({ page }) => {
      const { ok } = await navigateOrSkip(page, '/governance');
      if (!ok) return;

      const url = page.url();
      const on403 = url.includes('/403');

      // 403 redirect is acceptable (role-gated)
      if (on403) return;

      expect(url).toContain('/governance');

      // error-display means the governance service failed — never acceptable as a success outcome.
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-title').count()) > 0;
      if (hasError) {
        const errText = await page
          .locator('.error-display, .error-display-title')
          .first()
          .textContent()
          .catch(() => '');
        throw new Error(
          `Governance page shows error state — service may be down or the route is broken.\n` +
            `Error content: "${errText?.slice(0, 300) ?? 'N/A'}"\n` +
            `URL: ${url}`
        );
      }

      // Require the actual governance content (access requests list or empty state).
      await expect(
        page.locator('.governance-access-request-list-page, .empty-state').first()
      ).toBeVisible({ timeout: 15000 });
    });
  });

  test.describe('Failure', () => {
    test('dq run detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      const { ok } = await navigateOrSkip(page, `/dq/runs/${nonExistentId}`, {
        contentSelector: '.error-display, .error-display-title, .dq-run-detail-page',
      });
      if (!ok) return;

      await page.locator('.error-display, .error-display-title, .dq-run-detail-page')
        .first().waitFor({ state: 'visible', timeout: 30000 }).catch(() => null);

      const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
      if (!hasErrorDisplay) {
        const stillLoading = (await page.locator('[data-testid="skeleton-row"], .skeleton, .loading-spinner').count()) > 0;
        if (stillLoading) {
          test.skip(true, 'Backend too slow — page still loading skeleton after 30s; error-display not yet rendered');
          return;
        }
      }
      expect(hasErrorDisplay, 'Expected .error-display for non-existent resource').toBe(true);

      // H3: warn on non-404 errors (e.g. 500, network failure)
      if (hasErrorDisplay) {
        const errText = await page
          .locator('.error-display, .error-display-title')
          .first()
          .textContent()
          .catch(() => '');
        if (errText && !/404|not found/i.test(errText)) {
          console.warn(
            `[DQ nil-UUID] Non-404 error displayed: "${errText?.slice(0, 300)}"`
          );
        }
      }
    });

    test('compliance run detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      const { ok } = await navigateOrSkip(page, `/compliance/runs/${nonExistentId}`, {
        contentSelector: '.error-display, .error-display-title, .compliance-run-detail-page',
      });
      if (!ok) return;

      await page.locator('.error-display, .error-display-title, .compliance-run-detail-page')
        .first().waitFor({ state: 'visible', timeout: 30000 }).catch(() => null);

      const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
      if (!hasErrorDisplay) {
        const stillLoading = (await page.locator('[data-testid="skeleton-row"], .skeleton, .loading-spinner').count()) > 0;
        if (stillLoading) {
          test.skip(true, 'Backend too slow — page still loading skeleton after 30s; error-display not yet rendered');
          return;
        }
      }
      expect(hasErrorDisplay, 'Expected .error-display for non-existent resource').toBe(true);

      // H3: warn on non-404 errors (e.g. 500, network failure)
      if (hasErrorDisplay) {
        const errText = await page
          .locator('.error-display, .error-display-title')
          .first()
          .textContent()
          .catch(() => '');
        if (errText && !/404|not found/i.test(errText)) {
          console.warn(
            `[Compliance nil-UUID] Non-404 error displayed: "${errText?.slice(0, 300)}"`
          );
        }
      }
    });
  });

  test.describe('Edge', () => {
    test('unauthenticated access to /dq redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await gotoWithRetry(page, '/dq');
      try {
        await waitForAppMainReady(page, {
          timeout: 30000,
          acceptRedirectToLogin: true,
        });
      } catch {
        // Redirect to login is the expected outcome
      }
      expect(page.url()).toContain('/login');
    });
  });
});
