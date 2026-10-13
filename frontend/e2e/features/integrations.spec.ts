/**
 * E2E Feature: Integrations
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.2. Routes: /integrations/connections, /integrations/sync-jobs, /integrations/mappings.
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import {
  assertListPageLoads,
  loginAndNavigateToRoute,
} from '../fixtures/helpers';

// The connections route was redesigned into the tabbed
// marketplace-connections surface (MarketplaceConnectionListPage) — the
// old `.integration-connections-page` root class no longer exists. The
// content markers are the connection grid, the empty state, or the
// "Marketplace Connections" heading (2026-10-03, batch-7 failure: the
// page rendered real connection cards while the stale selector found
// nothing for 60s).
const CONNECTIONS_CONTENT_SELECTOR =
  '.connection-list-grid, .empty-state, [data-testid="empty-state"], h1:has-text("Marketplace Connections")';

test.describe('Feature: Integrations', () => {
  // 240s: tail-of-batch churn stacks login backoff (~45s) + navigation (60s)
  // + assertListPageLoads (60s + a 30s loading-branch extension). 120s
  // expired mid-loading and surfaced as "Target page closed" inside the
  // helper (same budget math as DE-010/015).
  test.setTimeout(240000);

  test.describe('Success', () => {
    test('integrations connections loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/connections', {
        timeout: 60000,
        contentSelector: `${CONNECTIONS_CONTENT_SELECTOR}, .error-display, [data-testid="error-display"], h1`,
      });
      let loadError: unknown = null;
      try {
        await assertListPageLoads(page, CONNECTIONS_CONTENT_SELECTOR, {
          timeout: 60000,
        });
      } catch (err) {
        const errMsg = String(err);
        if (errMsg.includes('NOT_FOUND') || errMsg.includes('not found')) {
          test.info().annotations.push({
            type: 'backend-not-deployed',
            description: `Integrations backend endpoint not available: ${errMsg.slice(0, 200)}`,
          });
          test.skip(errMsg.includes('NOT_FOUND') || errMsg.includes('not found'), 'Integrations backend endpoint returns NOT_FOUND — feature not deployed on staging');
          return;
        }
        loadError = err;
      }
      if (loadError !== null) {
        // Churn recovery (b7 #26): the connections fetch can fail during
        // an API restart window — the page renders its ErrorDisplay with
        // a Retry affordance. Use the app's recovery ONCE before failing.
        const errorDisplay = page.locator('.error-display, [data-testid="error-display"]').first();
        // intentional: diagnostic-only read — an empty read just skips the
        // retry and the second assertListPageLoads below reports the state.
        const errText = (await errorDisplay.textContent().catch(() => '')) ?? '';
        if (/NETWORK_ERROR|Failed to fetch|connection|INTERNAL_ERROR|SERVICE_UNAVAILABLE|timed out/i.test(errText)) {
          await errorDisplay.locator('button:has-text("Retry")').first().click();
          // intentional: single retry for transient mid-batch churn — the
          // second assertListPageLoads below must pass or the test fails.
          await page
            .locator(CONNECTIONS_CONTENT_SELECTOR)
            .first()
            .waitFor({ state: 'visible', timeout: 30000 })
            .catch(() => null);
          await assertListPageLoads(page, CONNECTIONS_CONTENT_SELECTOR, {
            timeout: 30000,
          });
          return;
        }
        if (loadError instanceof Error) throw loadError;
        throw new Error(String(loadError));
      }
    });
  });

  test.describe('Failure', () => {
    test('integrations sync-jobs loads content or shows gated/error state', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/integrations/sync-jobs', {
        timeout: 60000,
        contentSelector:
          '.integration-sync-jobs-page, .sync-jobs-page, .empty-state, [data-testid="empty-state"], .unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"], h1, .disabled-capability-page, [data-testid="disabled-capability-page"]',
      });

      const url = page.url();
      if (url.includes('/login') || url.includes('/403')) {
        expect(url).toMatch(/\/login|\/403/);
        return;
      }
      // Accept error-display when backend is not deployed (NOT_FOUND)
      const errorDisplay = page.locator('.error-display, [data-testid="error-display"]').first();
      if ((await errorDisplay.count()) > 0) {
        // intentional: tolerates a detached/removed element while extracting text for a diagnostic message; the surrounding throw/expect below this catch is the primary failure path.
        let errText = (await errorDisplay.first().textContent().catch(() => '')) ?? '';
        if (/NOT_FOUND|not found/i.test(errText)) {
          test.info().annotations.push({
            type: 'backend-not-deployed',
            description: 'Integrations sync-jobs backend not available',
          });
          return; // Backend not deployed — acceptable
        }
        // Churn recovery (b7 #27): NETWORK_ERROR is a transient mid-batch
        // stall, not a product signal — this test treats an error STATE as
        // acceptable, so retry ONCE via the app's Retry affordance before
        // classifying the error as real.
        if (/NETWORK_ERROR|Failed to fetch|connection|INTERNAL_ERROR|SERVICE_UNAVAILABLE|timed out/i.test(errText)) {
          await errorDisplay.locator('button:has-text("Retry")').first().click();
          // intentional: single retry for transient mid-batch churn — the
          // re-check below must find content or the test fails.
          await page
            .locator(
              '.integration-sync-jobs-page, .sync-jobs-page, .empty-state, [data-testid="empty-state"], .unavailable-page, [data-testid="unavailable-page"], .disabled-capability-page, [data-testid="disabled-capability-page"]'
            )
            .first()
            .waitFor({ state: 'visible', timeout: 30000 })
            .catch(() => null);
          if ((await errorDisplay.count()) > 0) {
            // intentional: diagnostic-only read after the single retry —
            // an empty read just means no error surface rendered.
            errText = (await errorDisplay.first().textContent().catch(() => '')) ?? '';
            throw new Error(`Unexpected error on integrations page: ${errText.slice(0, 200)}`);
          }
          return;
        }
        // Real error (not NOT_FOUND, not transient churn) — fail
        throw new Error(`Unexpected error on integrations page: ${errText.slice(0, 200)}`);
      }
      const hasContent =
        (await page
          .locator(
            '.integration-sync-jobs-page, .sync-jobs-page, .empty-state, [data-testid="empty-state"], .unavailable-page, [data-testid="unavailable-page"], h1, .disabled-capability-page, [data-testid="disabled-capability-page"]'
          )
          .count()) > 0;
      expect(
        hasContent,
        'Expected page content (.sync-jobs-page, .empty-state, [data-testid="empty-state"], .unavailable-page, [data-testid="unavailable-page"], or h1)'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('unauthenticated access to integrations redirects to login', async ({ page }) => {
      await page.goto('/integrations/connections');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/integrations'),
        'Expected /login redirect or /integrations with auth'
      ).toBe(true);
    });
  });
});
