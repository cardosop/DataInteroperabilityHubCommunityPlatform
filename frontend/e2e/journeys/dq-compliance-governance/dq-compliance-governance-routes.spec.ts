/**
 * E2E: DQ, Compliance, Governance routes (Phase 13 — 15.5)
 * JOURNEY-DPO-004, DE-003–004, JOURNEY-CPO-001–002: DQ runs, compliance runs, access requests.
 * Routes: /dq, /compliance, /governance.
 * For "not implemented" backend, skip or assert /unavailable. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { assertListPageLoads, waitForAppMainReady } from '../../fixtures/helpers';

test.describe('DQ, Compliance, Governance routes', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('dq list loads (runs list or empty)', async ({ page }) => {
      await page.goto('/dq');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          contentSelector: '.dq-run-list-page, .empty-state, .error-display',
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
      expect(page.url()).toContain('/dq');
      // error-display is not an acceptable success outcome for the DQ runs list
      await assertListPageLoads(page, '.dq-run-list-page, .empty-state');
    });

    test('compliance list loads (runs list or empty)', async ({ page }) => {
      await page.goto('/compliance');
      try {
        await waitForAppMainReady(page, {
          timeout: 60000,
          contentSelector: '.compliance-run-list-page, .empty-state, .error-display',
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
      expect(page.url()).toContain('/compliance');
      // error-display is not an acceptable success outcome for the compliance runs list
      await assertListPageLoads(page, '.compliance-run-list-page, .empty-state');
    });

    test('governance page loads (access requests or empty)', async ({ page }) => {
      await page.goto('/governance');
      await page.waitForLoadState('domcontentloaded');
      // AccessRequestListPage.tsx:60 renders .governance-access-request-list-page
      await page
        .locator('.governance-access-request-list-page, .empty-state, .error-display, .app-main, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 })
        .catch(() => null);
      const url = page.url();
      const on403 = url.includes('/403');
      const onLogin = url.includes('/login');

      // 403 and login redirects are acceptable (role-gated or unauthenticated)
      if (on403 || onLogin) return;

      expect(url).toContain('/governance');

      // error-display means the governance service failed — never acceptable as a success outcome.
      // .app-main alone is the generic app shell — it tells us nothing about page content.
      // Both of those were previously accepted; they are no longer.
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
      // AccessRequestListPage.tsx:60 renders .governance-access-request-list-page.
      await expect(
        page.locator('.governance-access-request-list-page, .empty-state').first()
      ).toBeVisible({ timeout: 15000 });
    });
  });

  test.describe('Failure', () => {
    test('dq run detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      // Added .catch(() => null) — without it a login redirect causes a 60s hard timeout.
      // Only 404 is valid; 200 means the DQ run exists (backend bug).
      const responsePromise = page.waitForResponse(
        (resp) =>
          resp.url().includes(`/dq/runs/${nonExistentId}`) &&
          resp.status() === 404,
        { timeout: 15000 }
      ).catch(() => null);
      await page.goto(`/dq/runs/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await responsePromise;

      await page.locator('.error-display, .error-display-title, .dq-run-detail-page')
        .first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);

      const onLogin = page.url().includes('/login');
      if (onLogin) return;

      const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
      const hasNotFoundText = (await page.locator('.error-display-message').filter({ hasText: /not found|could not be found|404|matches the given query/i }).count()) > 0;
      if (hasErrorDisplay && !hasNotFoundText) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`DQ run detail shows non-404 error for nil UUID: "${errText?.slice(0, 200)}". Expected "not found".`);
      }
      expect(hasErrorDisplay && hasNotFoundText).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('compliance run detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      // Added .catch(() => null) — without it a login redirect causes a 60s hard timeout.
      const responsePromise = page.waitForResponse(
        (resp) =>
          resp.url().includes(`/compliance/runs/${nonExistentId}`) &&
          resp.status() === 404,
        { timeout: 15000 }
      ).catch(() => null);
      await page.goto(`/compliance/runs/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await responsePromise;

      await page.locator('.error-display, .error-display-title, .compliance-run-detail-page')
        .first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);

      const onLogin = page.url().includes('/login');
      if (onLogin) return;

      const hasErrorDisplay = (await page.locator('.error-display, .error-display-title').count()) > 0;
      const hasNotFoundText = (await page.locator('.error-display-message').filter({ hasText: /not found|could not be found|404|matches the given query/i }).count()) > 0;
      if (hasErrorDisplay && !hasNotFoundText) {
        const errText = await page.locator('.error-display, .error-display-title').first().textContent().catch(() => '');
        throw new Error(`Compliance run detail shows non-404 error for nil UUID: "${errText?.slice(0, 200)}". Expected "not found".`);
      }
      expect(hasErrorDisplay && hasNotFoundText).toBe(true);
    });
  });
});
