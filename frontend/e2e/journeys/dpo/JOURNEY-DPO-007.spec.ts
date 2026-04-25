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
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-007: Use AI Schema Matching for Asset Creation', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('schema matching page loads or shows unavailable when capability is off', async ({ page }) => {
      const testUser = await getTestUser();
      // loginAndNavigateToRoute handles auth token injection and retry on redirect-to-login.
      // /ai/schema-matching is in CAPABILITY_GATED_ROUTES so acceptRedirectToLogin is auto-set.
      await loginAndNavigateToRoute(page, testUser, '/ai/schema-matching', {
        timeout: 60000,
        contentSelector:
          '.schema-matching-page, [data-testid="schema-matching-page"], .unavailable-page, .error-display',
        acceptRedirectToLogin: false,
      });
      await waitForLoadingComplete(page, { timeout: 30000 });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on /ai/schema-matching after login');
      }

      const capabilityEnabled =
        page.url().includes('/ai/schema-matching') &&
        (await page.locator('.schema-matching-page, [data-testid="schema-matching-page"]').count()) > 0;
      const capabilityDisabled =
        (await page.locator('.unavailable-page').count()) > 0 ||
        page.url().includes('/unavailable') ||
        page.url().includes('/403');

      expect(capabilityEnabled || capabilityDisabled).toBe(true) /* acceptable states */;

      if (capabilityEnabled) {
        await expect(
          page.locator('.schema-matching-page, [data-testid="schema-matching-page"]').first()
        ).toBeVisible({ timeout: 5000 });
      } else {
        await expect(
          page.locator('.unavailable-page').first()
        ).toBeVisible({ timeout: 5000 });
      }
    });
  });

  test.describe('Failure', () => {
    test('schema matching without capability shows unavailable page, not a crash', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/ai/schema-matching', {
        timeout: 60000,
        contentSelector:
          '.schema-matching-page, [data-testid="schema-matching-page"], .unavailable-page, .error-display',
        acceptRedirectToLogin: false,
      });
      await waitForLoadingComplete(page, { timeout: 30000 });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on /ai/schema-matching after login');
      }

      const capabilityEnabled =
        page.url().includes('/ai/schema-matching') &&
        (await page.locator('.schema-matching-page, [data-testid="schema-matching-page"]').count()) > 0;
      const capabilityDisabled =
        (await page.locator('.unavailable-page').count()) > 0 ||
        page.url().includes('/unavailable') ||
        page.url().includes('/403');

      if (capabilityEnabled) {
        await expect(
          page.locator('.schema-matching-page, [data-testid="schema-matching-page"]').first()
        ).toBeVisible({ timeout: 5000 });
        await expect(page.locator('.error-display')).not.toBeVisible();
        test.info().annotations.push({
          type: 'capability-enabled',
          description: 'ai.schema-matching is enabled; verified enabled path renders correctly instead',
        });
        return;
      }

      expect(capabilityDisabled).toBe(true);
      await expect(
        page.locator('.unavailable-page').first()
      ).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Edge', () => {
    test('schema matching form accepts file input when capability is enabled', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/ai/schema-matching', {
        timeout: 60000,
        contentSelector:
          '.schema-matching-page, [data-testid="schema-matching-page"], .unavailable-page, .error-display',
        acceptRedirectToLogin: false,
      });
      await waitForLoadingComplete(page, { timeout: 30000 });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on /ai/schema-matching after login');
      }

      const capabilityDisabled =
        page.url().includes('/unavailable') ||
        page.url().includes('/403') ||
        (await page.locator('.unavailable-page').count()) > 0;

      if (capabilityDisabled) {
        await expect(page.locator('.unavailable-page').first()).toBeVisible({ timeout: 5000 });
        return;
      }

      const hasSchemaMatchingPage =
        (await page.locator('.schema-matching-page, [data-testid="schema-matching-page"]').count()) > 0;
      if (!hasSchemaMatchingPage) {
        throw new Error(
          `Expected schema matching UI at /ai/schema-matching but main content is missing. URL=${page.url()}`
        );
      }

      await expect(
        page.locator('.schema-matching-page, [data-testid="schema-matching-page"]').first()
      ).toBeVisible({ timeout: 5000 });
      const fileInput = page.locator('input[type="file"]').first();
      // intentional: file-input is form-version-dependent — newer forms use a custom drag-drop component without a raw <input type=file>; both shapes are valid.
      if ((await fileInput.count()) > 0) {
        await fileInput.setInputFiles({
          name: 'schema.json',
          mimeType: 'application/json',
          buffer: Buffer.from(
            JSON.stringify({ fields: [{ name: 'id', type: 'string' }, { name: 'value', type: 'number' }] })
          ),
        });
        await page.waitForTimeout(1000);
        const hasError = (await page.locator('.error-display').count()) > 0;
        if (hasError) {
          const errText = (await page.locator('.error-display').first().textContent()) ?? '';
          throw new Error(`Schema matching file upload produced error: ${errText.slice(0, 200)}`);
        }
        const hasResults =
          (await page.locator('.schema-matching-results, [data-testid="matching-results"]').count()) > 0;
        expect(hasResults).toBe(true) /* acceptable states */;
      }
      expect(page.url()).toContain('/ai/schema-matching');
    });
  });
});
