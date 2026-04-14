/**
 * E2E Feature: Webhooks
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /webhooks.
 * At least Success + one Failure or Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { assertListPageLoads } from '../fixtures/helpers';

test.describe('Feature: Webhooks', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('webhooks list loads', async ({ page }) => {
      await page.goto('/webhooks');
      await page.waitForLoadState('domcontentloaded');
      await assertListPageLoads(page, '.webhook-list-page, .empty-state, h1', { timeout: 60000 });
    });
  });

  test.describe('Failure', () => {
    test('webhook detail with non-existent id shows error or redirect', async ({ page }) => {
      // Wait for the actual API response that settles the React Query rather
      // than a fixed 5 s sleep — staging cold-start can push the first request
      // beyond 5 s and the previous fixed wait raced the loading skeleton.
      //
      // The webhook detail endpoint lives at `/api/v1/webhooks/webhooks/{id}/`
      // (the WEBHOOKS_BASE_PATH constant is `webhooks/webhooks` — see
      // frontend/src/features/webhooks/services/webhookService.ts:16). Match
      // the doubled segment so we don't accidentally wait on the list endpoint
      // or never match. The URL may carry a query string, so don't anchor `$`.
      const NIL_UUID = '00000000-0000-0000-0000-000000000000';
      const detailApiDone = page.waitForResponse(
        (r) =>
          new RegExp(`/api/v1/webhooks/webhooks/${NIL_UUID}/?(\\?|$)`).test(r.url()) &&
          r.status() !== 401,
        { timeout: 60_000 }
      );

      await page.goto(`/webhooks/${NIL_UUID}`, {
        waitUntil: 'domcontentloaded',
        timeout: 60_000,
      });

      // Either the API responded (deterministic) or the SPA redirected to login
      // before the request fired (also acceptable). `.catch(() => null)` keeps
      // the test resilient to the redirect path.
      await detailApiDone.catch((err) =>
        console.log(`Webhook detail API wait: ${(err as Error).message?.slice(0, 100)}`)
      );

      // After the query settles, React renders either the ErrorDisplay (4xx/5xx)
      // or stays on the skeleton (200 + null body). Wait for one of the terminal
      // UI states before asserting.
      await page
        .locator('.error-display, .webhook-detail-page')
        .first()
        .waitFor({ state: 'visible', timeout: 15_000 })
        .catch((err) =>
          console.log(`Webhook detail UI wait: ${(err as Error).message?.slice(0, 100)}`)
        );

      if (page.url().includes('/login')) {
        test.skip(true, 'Auth redirect — session expired before webhook detail loaded');
        return;
      }
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|404/i').count()) > 0;
      expect(hasError).toBe(true);
    });
  });
});
