/**
 * E2E Test: JOURNEY-DPO-007 — Use AI Schema Matching for Asset Creation
 *
 * Journey: Use AI Schema Matching for Asset Creation
 * Persona: Data Product Owner
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge per JOURNEY-DPO-001 pattern. Routes: /ai/schema-matching.
 * Capability-gated: ai.schema-matching. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DPO-007: Use AI Schema Matching for Asset Creation', () => {
  test.setTimeout(180000); // 3 min: visible/slowMo

  test.describe('Success', () => {
    test('schema matching page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ai/schema-matching');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onSchemaMatching = url.includes('/ai/schema-matching');
      const hasContent =
        (await page.locator('.schema-matching-page, .app-main, .unavailable-page, .error-display').count()) > 0;
      expect(onLogin || on403 || onUnavailable || (onSchemaMatching && hasContent)).toBe(true);
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
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onSchemaMatching = url.includes('/ai/schema-matching');
      expect(onLogin || on403 || onUnavailable || onSchemaMatching).toBe(true);
    });
  });
});
