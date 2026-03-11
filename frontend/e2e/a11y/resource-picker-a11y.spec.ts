/**
 * Resource Picker Accessibility Tests (axe-core) — authenticated
 * Per task 29.69.3.5. Runs with stored auth session (storageState from setup-auth project).
 *
 * Tests the authenticated dataset-create page (which contains the AssetPicker component)
 * and the assets list page for WCAG 2 AA compliance.
 *
 * Depends on: setup-auth project (playwright.config.ts storageState).
 */
import { AxeBuilder } from '@axe-core/playwright';
import { expect } from '@playwright/test';
import { test } from '@playwright/test';

test.describe('Resource Picker Accessibility (axe) — authenticated', () => {
  test.setTimeout(90000);

  test('dataset create page (with AssetPicker) has no critical a11y violations', async ({
    page,
  }) => {
    await page.goto('/datasets/create?linkMode=existing');
    await page.waitForLoadState('domcontentloaded');
    // Wait for either the create form or a redirect (when storedAuth is present the form renders)
    await page
      .locator('.dataset-create-page, .app-main, #email')
      .first()
      .waitFor({ state: 'visible', timeout: 30000 })
      .catch(() => null);

    if (page.url().includes('/login')) {
      // storedState auth expired — skip rather than reporting false violations on login page
      test.skip(true, 'Stored auth redirected to login; re-run after setup-auth completes');
      return;
    }

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();
    expect(results.violations).toEqual([]);
  });

  test('assets list page has no critical a11y violations', async ({ page }) => {
    await page.goto('/assets');
    await page.waitForLoadState('domcontentloaded');
    await page
      .locator('.asset-list-page, .empty-state, .app-main, #email')
      .first()
      .waitFor({ state: 'visible', timeout: 30000 })
      .catch(() => null);

    if (page.url().includes('/login')) {
      test.skip(true, 'Stored auth redirected to login; re-run after setup-auth completes');
      return;
    }

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();
    expect(results.violations).toEqual([]);
  });
});
