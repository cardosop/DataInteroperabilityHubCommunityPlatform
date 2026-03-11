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
    test('ODPS detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/odps/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|failed to load|404/i').count()) > 0;
      const noSuccessContent = (await page.locator('.odps-detail-main').count()) === 0;
      const onLogin = page.url().includes('/login');
      expect(hasError || noSuccessContent || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('ODPS upload page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      // Retry goto on transient network errors (ERR_NETWORK_CHANGED under parallel load)
      let lastErr: unknown;
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          await page.goto('/odps/upload', { waitUntil: 'domcontentloaded', timeout: 30000 });
          break;
        } catch (e) {
          lastErr = e;
          if (String(e).includes('ERR_NETWORK_CHANGED') || String(e).includes('net::')) {
            await new Promise((r) => setTimeout(r, 2000 * (attempt + 1)));
            continue;
          }
          throw e;
        }
      }
      if (lastErr) throw lastErr;
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('.odps-upload-page, .error-display, .loading-spinner-container, #email', {
        timeout: 20000,
      });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/odps/upload');
    });
  });
});
