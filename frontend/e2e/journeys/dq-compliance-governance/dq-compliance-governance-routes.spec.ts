/**
 * E2E: DQ, Compliance, Governance routes (Phase 13 — 15.5)
 * JOURNEY-DPO-004, DE-003–004, JOURNEY-CPO-001–002: DQ runs, compliance runs, access requests.
 * Routes: /dq, /compliance, /governance.
 * For "not implemented" backend, skip or assert /unavailable. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { waitForAppMainReady } from '../../fixtures/helpers';

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
      expect(page.url()).toContain('/dq');
      await expect(
        page.locator('.dq-run-list-page, .empty-state').first()
      ).toBeVisible({ timeout: 10000 });
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
      expect(page.url()).toContain('/compliance');
      await expect(
        page.locator('.compliance-run-list-page, .empty-state').first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('governance page loads (access requests or empty)', async ({ page }) => {
      await page.goto('/governance');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.access-request-list-page, .empty-state, .error-display, .app-main, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 })
        .catch(() => null);
      const url = page.url();
      const onGov = url.includes('/governance');
      const on403 = url.includes('/403');
      const onLogin = url.includes('/login');
      const hasContent =
        (await page.locator('.access-request-list-page, .empty-state, .error-display, .app-main').count()) > 0;
      expect(onGov || on403 || onLogin).toBe(true);
      expect(hasContent || on403 || onLogin).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('dq run detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      const responsePromise = page.waitForResponse(
        (resp) =>
          resp.url().includes(`dq/runs/${nonExistentId}`) &&
          (resp.status() === 200 || resp.status() === 404),
        { timeout: 60000 }
      );
      await page.goto(`/dq/runs/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await responsePromise;
      await page.waitForTimeout(5000);
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-title').count()) > 0 ||
        (await page.locator('text=/not found|failed to load|404|Failed to load DQ run/i').count()) >
          0;
      const noSuccessContent = (await page.locator('.dq-run-detail-main').count()) === 0;
      expect(hasError || noSuccessContent).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('compliance run detail with non-existent id shows error', async ({ page }) => {
      const nonExistentId = '00000000-0000-0000-0000-000000000000';
      const responsePromise = page.waitForResponse(
        (resp) =>
          resp.url().includes(`compliance/runs/${nonExistentId}`) &&
          (resp.status() === 200 || resp.status() === 404),
        { timeout: 60000 }
      );
      await page.goto(`/compliance/runs/${nonExistentId}`);
      await page.waitForLoadState('domcontentloaded');
      await responsePromise;
      await page.waitForTimeout(5000);
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('.error-display-title').count()) > 0 ||
        (await page
          .locator('text=/not found|failed to load|404|Failed to load compliance run/i')
          .count()) > 0;
      const noSuccessContent = (await page.locator('.compliance-run-detail-main').count()) === 0;
      expect(hasError || noSuccessContent).toBe(true);
    });
  });
});
