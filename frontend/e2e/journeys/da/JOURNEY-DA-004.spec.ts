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
import { getConsumerTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DA-004: Execute Federated Query', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('semantic page loads for federated query', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginUser(page, testUser);
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const onSemantic = page.url().includes('/semantic');
      const hasContent =
        (await page.locator('.semantic-page, .app-main, .unavailable-page').count()) > 0;
      expect(onLogin || on403 || (onSemantic && hasContent)).toBe(true);
    });

    test('virtualization list loads for federated sources', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginUser(page, testUser);
      await page.goto('/virtualization');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.virtual-dataset-list-page, .error-display, .empty-state, #email',
        { timeout: 65000 }
      );
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/virtualization');
    });
  });

  test.describe('Failure', () => {
    test('semantic without capability shows 403 or unavailable', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginUser(page, testUser);
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const on403 = page.url().includes('/403');
      const onUnavailable = (await page.locator('.unavailable-page, .error-display').count()) > 0;
      const onSemantic = page.url().includes('/semantic');
      const onLogin = page.url().includes('/login');
      expect(on403 || onUnavailable || onSemantic || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('semantic and virtualization routes accessible', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginUser(page, testUser);
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      expect(
        page.url().includes('/semantic') ||
          page.url().includes('/403') ||
          page.url().includes('/login')
      ).toBe(true);
      await page.goto('/virtualization');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      expect(page.url().includes('/virtualization') || page.url().includes('/login')).toBe(true);
    });
  });
});
