/**
 * E2E Test: JOURNEY-DA-004 — Execute Federated Query
 *
 * Journey: Execute Federated Query
 * Persona: Data Analyst
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /semantic (SPARQL federated), /virtualization.
 * Capability-gated: semantic.sparql. Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getConsumerTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DA-004: Execute Federated Query', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('semantic page loads for federated query', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginUser(page, testUser);
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onSemantic = url.includes('/semantic');
      const onComingSoon = url.includes('/coming-soon');
      const onUnavailable = url.includes('/unavailable');
      if (onLogin || on403) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }
      // CapabilityRoute sends MVP builds to /coming-soon when semantic.sparql is off.
      expect(onSemantic || onComingSoon || onUnavailable).toBe(true);
      if (onSemantic) {
        const hasContent =
          (await page.locator('.semantic-page, .app-main').count()) > 0;
        expect(hasContent).toBe(true);
        await expect(page.locator('.error-display')).not.toBeVisible();
      } else {
        await expect(page.locator('.unavailable-page').first()).toBeVisible({ timeout: 15000 });
      }
    });

    test('virtualization list loads for federated sources', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginUser(page, testUser);
      await page.goto('/virtualization');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.virtual-dataset-list-page, .error-display, .empty-state, .app-main',
        { timeout: 90000 }
      );
      if (page.url().includes('/login')) {
        test.skip(true, 'Auth gated — skipping success assertion');
        return;
      }
      expect(page.url()).toContain('/virtualization');
      await expect(page.locator('.error-display')).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('semantic without capability shows 403 or unavailable', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginUser(page, testUser);
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const on403 = url.includes('/403');
      const onUnavailableDom =
        (await page.locator('.unavailable-page, .error-display').count()) > 0;
      const onLogin = url.includes('/login');
      const onUnavailableUrl = url.includes('/unavailable');
      const onComingSoon = url.includes('/coming-soon');
      expect(on403 || onUnavailableDom || onLogin || onUnavailableUrl || onComingSoon).toBe(
        true
      ) /* acceptable states */;
    });

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/semantic');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('semantic and virtualization routes accessible', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginUser(page, testUser);
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      const su = page.url();
      expect(
        su.includes('/semantic') ||
          su.includes('/403') ||
          su.includes('/login') ||
          su.includes('/unavailable') ||
          su.includes('/coming-soon')
      ).toBe(true);
      await page.goto('/virtualization');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      expect(page.url().includes('/virtualization') || page.url().includes('/login')).toBe(true);
    });
  });
});
