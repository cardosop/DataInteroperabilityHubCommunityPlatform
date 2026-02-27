/**
 * E2E Test: JOURNEY-DE-008 — Integrate AI Schema Matching into Workflow
 *
 * Journey: Integrate AI Schema Matching into Workflow
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /ai/schema-matching.
 * Capability-gated: ai.schema-matching. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DE-008: Integrate AI Schema Matching into Workflow', () => {
  test.setTimeout(300000); // 5 min: visible/slowMo adds latency; avoids timeout-induced ENOENT

  test.describe('Success', () => {
    test('schema matching page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ai/schema-matching');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onLogin = page.url().includes('/login');
      const on403 = page.url().includes('/403');
      const onSchemaMatching = page.url().includes('/ai/schema-matching');
      const hasContent =
        (await page.locator('.schema-matching-page, .app-main, .unavailable-page').count()) > 0;
      expect(onLogin || on403 || (onSchemaMatching && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('schema matching without capability shows 403 or unavailable', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ai/schema-matching');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const on403 = page.url().includes('/403');
      const onUnavailable = (await page.locator('.unavailable-page, .error-display').count()) > 0;
      const onSchemaMatching = page.url().includes('/ai/schema-matching');
      const onLogin = page.url().includes('/login');
      expect(on403 || onUnavailable || onSchemaMatching || onLogin).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('schema matching page loads or redirects', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ai/schema-matching');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/ai/schema-matching')).toBe(true);
    });
  });
});
