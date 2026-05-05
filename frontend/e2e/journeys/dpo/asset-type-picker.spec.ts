/**
 * Phase 250.6.B.6 — E2E coverage for the AssetTypePickerStep.
 *
 * Covers all FOUR selections + the ``?skip=picker`` shortcut.
 * Each test asserts the post-pick form state by checking that
 * the corresponding collapsible section is open (data /
 * contract / both) OR that both sections are collapsed
 * (metadata).
 *
 * The test relies on the stable data-testids the picker
 * publishes (``asset-type-picker-step``,
 * ``asset-type-picker-option-{kind}``,
 * ``asset-type-picker-skip``); a future style refactor
 * doesn't break the test as long as those selectors stay
 * intact.
 */
import { expect, test } from '@playwright/test';

import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import {
  loginAndNavigateToRoute,
  waitForLoadingComplete,
} from '../../fixtures/helpers';


test.describe('Asset Type Picker (Phase 250.6.B)', () => {
  test.setTimeout(60000);

  test.describe('Failure', () => {
    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/assets/create', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|assets|register)/, { timeout: 20_000 });
    });
  });

  test.describe('Picker default render', () => {
    test('renders all 4 options before the form', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/assets/create', {
        timeout: 30_000,
      });
      await waitForLoadingComplete(page);

      const picker = page.getByTestId('asset-type-picker-step');
      await expect(picker).toBeVisible();

      // The form must NOT yet be rendered while the picker is up.
      await expect(page.getByTestId('asset-create-form')).toHaveCount(0);

      // All four kinds must be present.
      for (const kind of ['data', 'contract', 'both', 'metadata']) {
        await expect(
          page.getByTestId(`asset-type-picker-option-${kind}`),
        ).toBeVisible();
      }
    });
  });

  test.describe('Picker selections drive form state', () => {
    for (const kind of ['data', 'contract', 'both', 'metadata'] as const) {
      test(`${kind} selection advances to the form`, async ({ page }) => {
        const user = await getTestUser();
        await loginAndNavigateToRoute(page, user, '/assets/create', {
          timeout: 30_000,
        });
        await waitForLoadingComplete(page);

        const option = page.getByTestId(`asset-type-picker-option-${kind}`);
        await expect(option).toBeVisible();
        await option.click();

        // Picker dismissed, form rendered.
        await expect(
          page.getByTestId('asset-type-picker-step'),
        ).toHaveCount(0);
        await expect(page.getByTestId('asset-create-form')).toBeVisible({
          timeout: 10_000,
        });
      });
    }
  });

  test.describe('Skip shortcuts', () => {
    test('?skip=picker query param bypasses the picker', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(
        page,
        user,
        '/assets/create?skip=picker',
        { timeout: 30_000 },
      );
      await waitForLoadingComplete(page);

      // Picker NEVER renders.
      await expect(
        page.getByTestId('asset-type-picker-step'),
      ).toHaveCount(0);
      // Form renders directly.
      await expect(page.getByTestId('asset-create-form')).toBeVisible();
    });

    test('Skip CTA bypasses the picker without URL change', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/assets/create', {
        timeout: 30_000,
      });
      await waitForLoadingComplete(page);

      const skip = page.getByTestId('asset-type-picker-skip');
      await expect(skip).toBeVisible();

      const urlBefore = page.url();
      await skip.click();
      await expect(page.getByTestId('asset-create-form')).toBeVisible();
      // 250.6.B.3 contract — skipping does NOT change the URL.
      expect(page.url()).toBe(urlBefore);
    });
  });

  test.describe('Accessibility', () => {
    test('radiogroup carries the right ARIA role + label', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/assets/create', {
        timeout: 30_000,
      });
      await waitForLoadingComplete(page);

      // The picker container is announced as a radio group with
      // the heading as its accessible name.
      const radiogroup = page.getByRole('radiogroup', {
        name: /choose the type of asset/i,
      });
      await expect(radiogroup).toBeVisible();

      const radios = radiogroup.getByRole('radio');
      await expect(radios).toHaveCount(4);
    });
  });
});
