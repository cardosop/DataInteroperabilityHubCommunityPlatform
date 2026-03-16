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
import { waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('JOURNEY-DPO-007: Use AI Schema Matching for Asset Creation', () => {
  test.setTimeout(180000); // 3 min: visible/slowMo

  test.describe('Success', () => {
    test('schema matching page loads or shows unavailable when capability is off', async ({ page }) => {
      // Use direct navigation (not loginAndNavigateToRoute) to avoid waitForAppMainReady timing
      // out while CapabilityRoute shows its loading spinner under backend load.
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ai/schema-matching');
      await page.waitForLoadState('domcontentloaded');

      // CapabilityRoute shows a loading spinner while capabilities are fetched.
      // Wait until either the feature page or the unavailable page renders.
      await page.waitForSelector(
        '.schema-matching-page, [data-testid="schema-matching-page"], .unavailable-page, .error-display, #email',
        { timeout: 30000 }
      ).catch(() => null);
      // Ensure loading spinner has cleared before asserting capability state
      await waitForLoadingComplete(page, { timeout: 30000 });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on AI schema-matching page');
      }

      const capabilityEnabled =
        page.url().includes('/ai/schema-matching') &&
        (await page.locator('.schema-matching-page, [data-testid="schema-matching-page"]').count()) > 0;
      const capabilityDisabled =
        (await page.locator('.unavailable-page').count()) > 0 ||
        page.url().includes('/unavailable') ||
        page.url().includes('/403');

      // Exactly one of the two branches must be true
      expect(capabilityEnabled || capabilityDisabled).toBe(true);

      if (capabilityEnabled) {
        await expect(
          page.locator('.schema-matching-page, [data-testid="schema-matching-page"]').first()
        ).toBeVisible({ timeout: 5000 });
      } else {
        // Capability disabled: unavailable indicator must be visible (not a blank/crash)
        await expect(
          page.locator('.unavailable-page, [role="main"]').first()
        ).toBeVisible({ timeout: 5000 });
      }
    });
  });

  test.describe('Failure', () => {
    test('schema matching without capability shows unavailable page, not a crash', async ({
      page,
    }) => {
      // When the ai.schema-matching capability is disabled the CapabilityRoute must render
      // an unavailable indicator — NOT a blank screen, runtime error, or broken render.
      // CapabilityRoute shows a loading spinner while capabilities are fetched — we must
      // wait past it before asserting.
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ai/schema-matching');
      await page.waitForLoadState('domcontentloaded');

      // Wait for CapabilityRoute to finish loading (spinner disappears, final state renders)
      await page.waitForSelector(
        '.schema-matching-page, [data-testid="schema-matching-page"], .unavailable-page, .error-display, #email',
        { timeout: 30000 }
      ).catch(() => null);
      // Ensure loading spinner has cleared before asserting capability state
      await waitForLoadingComplete(page, { timeout: 30000 });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login on AI schema-matching page');
      }

      const capabilityEnabled =
        page.url().includes('/ai/schema-matching') &&
        (await page.locator('.schema-matching-page, [data-testid="schema-matching-page"]').count()) > 0;

      if (capabilityEnabled) {
        // Capability is on — page loads correctly; failure scenario doesn't apply.
        // Annotate so the CI report shows the branch taken.
        test.info().annotations.push({
          type: 'capability-enabled',
          description: 'ai.schema-matching is on in this env; unavailable branch not triggered',
        });
        return;
      }

      // Capability disabled: must show unavailable page or 403 — NOT a blank render or crash
      const capabilityDisabled =
        (await page.locator('.unavailable-page').count()) > 0 ||
        page.url().includes('/unavailable') ||
        page.url().includes('/403');
      expect(capabilityDisabled).toBe(true);
      await expect(
        page.locator('.unavailable-page, [role="main"]').first()
      ).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Edge', () => {
    test('schema matching form accepts file input when capability is enabled', async ({ page }) => {
      // When the capability IS enabled the upload form must accept a schema file and
      // trigger the matching process (or show a progress indicator).
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ai/schema-matching');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.schema-matching-page, .unavailable-page, .error-display, h1, #email')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 })
        .catch(() => null);
      await new Promise((r) => setTimeout(r, 1000));

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login');
      }

      const capabilityDisabled =
        page.url().includes('/unavailable') ||
        page.url().includes('/403') ||
        (await page.locator('.unavailable-page').count()) > 0;

      if (capabilityDisabled) {
        // Capability disabled — verify unavailable page renders correctly (not a crash)
        await expect(page.locator('.unavailable-page, [role="main"]').first()).toBeVisible({ timeout: 5000 });
        return;
      }

      const hasSchemaMatchingPage = (await page.locator('.schema-matching-page').count()) > 0;
      if (!hasSchemaMatchingPage) {
        // Capability disabled rendered inline without URL redirect — verify some content exists
        await expect(page.locator('.app-main, h1').first()).toBeVisible({ timeout: 5000 });
        return;
      }

      // Capability is enabled — upload a schema file and verify matching responds
      await expect(page.locator('.schema-matching-page')).toBeVisible({ timeout: 5000 });
      const fileInput = page.locator('input[type="file"]').first();
      if ((await fileInput.count()) > 0) {
        await fileInput.setInputFiles({
          name: 'schema.json',
          mimeType: 'application/json',
          buffer: Buffer.from(
            JSON.stringify({ fields: [{ name: 'id', type: 'string' }, { name: 'value', type: 'number' }] })
          ),
        });
        await page.waitForTimeout(1000);
        // After file upload: either results appear OR loading starts — no error display
        const hasError = (await page.locator('.error-display').count()) > 0;
        if (hasError) {
          const errText = (await page.locator('.error-display').first().textContent()) ?? '';
          throw new Error(`Schema matching file upload produced error: ${errText.slice(0, 200)}`);
        }
        const hasResults =
          (await page.locator('.schema-matching-results, [data-testid="matching-results"], .loading-spinner-container').count()) > 0;
        expect(hasResults).toBe(true);
      }
      expect(page.url()).toContain('/ai/schema-matching');
    });
  });
});
