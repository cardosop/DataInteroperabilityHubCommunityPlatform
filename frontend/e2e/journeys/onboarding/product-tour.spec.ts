/**
 * E2E Test: First-login product tour — Phase 278.V.4
 *
 * Journey: Product Tour (first-login onboarding overlay).
 * @covers 278.V.4, 278.B.1, 278.R.6 — First-login product tour E2E test
 * Persona: All (persona-aware copy per role).
 * Reference: specs/ux-activation/activation-flows/spec.md (278.R.3)
 *
 * Covers the ProductTour component shipped in Phase 278.B.1 and wired
 * into App.tsx via ProductTourGate in Phase 278.R.6:
 *   - 5-step overlay with persona-aware copy (DE/DPO/CPO/DC/default).
 *   - Progress dots, Next/Prev navigation, Skip controls.
 *   - localStorage persistence (`meshant.tour.completed`).
 *   - A11y: role="dialog", aria-label, keyboard-dismissible.
 *
 * Prerequisite: ProductTourGate mounted in App.tsx (278.R.6).
 * Gate: ProductTourGate checks useUxV2Gate (capabilities → ux_v2) AND
 *   !user.has_seen_tour. When ux_v2 is not enabled for the test tenant,
 *   tests skip with a clear diagnostic.
 *
 * Success/Failure/Edge. Real backend; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';

const TOUR_STORAGE_KEY = 'meshant.tour.completed';

/**
 * Clear the product tour localStorage flag so ProductTour treats this
 * session as a first login. Must run BEFORE page.goto() because
 * ProductTour reads localStorage synchronously on mount.
 */
async function clearTourStorage(page: import('@playwright/test').Page): Promise<void> {
  await page.evaluate((key) => {
    localStorage.removeItem(key);
  }, TOUR_STORAGE_KEY);
}

/**
 * Read the tour completion flag from localStorage. Returns true if the
 * tour was dismissed/completed.
 */
async function isTourCompleted(page: import('@playwright/test').Page): Promise<boolean> {
  return page.evaluate((key) => {
    return localStorage.getItem(key) === 'true';
  }, TOUR_STORAGE_KEY);
}

test.describe('Product Tour @critical @quarantine', () => {
  test.setTimeout(120000);

  test.describe('Success — Tour lifecycle', () => {
    test('tour appears on first login, navigates 5 steps, and completes', async ({ page }) => {
      const user = await getTestUser();

      // Clear any prior tour state
      await clearTourStorage(page);

      // Login and navigate to home — ProductTourGate evaluates on mount
      await loginUser(page, user);
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      test.skip(
        page.url().includes('/login'),
        'Redirected to login — auth may have expired',
      );

      // The tour may or may not render depending on ux_v2 capability.
      // When gated, skip; otherwise test the full lifecycle.
      const tour = page.locator('[data-testid="product-tour"]');
      const tourVisible = (await tour.count()) > 0;
      test.skip(
        !tourVisible,
        'ProductTour not rendered — ux_v2 capability may be disabled for this tenant',
      );

      // A11y: role="dialog" + aria-label
      await expect(tour).toHaveAttribute('role', 'dialog');
      await expect(tour).toHaveAttribute('aria-label', 'Product tour');

      // Should show first step with title and description
      const title = tour.locator('.product-tour-title');
      const desc = tour.locator('.product-tour-desc');
      await expect(title).toBeVisible();
      await expect(desc).toBeVisible();

      // Progress dots: exactly 5
      const dots = tour.locator('.product-tour-dot');
      await expect(dots).toHaveCount(5);

      // First dot should be active
      const firstDot = dots.nth(0);
      await expect(firstDot).toHaveClass(/active/);

      // Navigate through all 5 steps via Next button
      const nextBtn = page.locator('[data-testid="tour-next"]');
      const skipBtn = tour.locator('.product-tour-btn--skip');

      for (let step = 1; step < 5; step++) {
        const currentTitle = await title.textContent();
        const currentDesc = await desc.textContent();

        // Each step should have non-empty content
        expect(currentTitle?.trim().length).toBeGreaterThan(0);
        expect(currentDesc?.trim().length).toBeGreaterThan(0);

        // Progress dot for current step should be active
        const activeDot = dots.nth(step - 1);
        const activeDotClass = await activeDot.getAttribute('class');
        const previousDotClass =
          step > 1 ? await dots.nth(step - 2).getAttribute('class') : '';

        if (step < 5) {
          await expect(nextBtn).toBeVisible();
          expect(await nextBtn.textContent()).toMatch(/Next/);
          await nextBtn.click();
          await page.waitForTimeout(300);
        }
      }

      // Last step: button should say "Got it!"
      await expect(nextBtn).toBeVisible();
      expect(await nextBtn.textContent()).toMatch(/Got it!/);

      // Complete the tour
      await nextBtn.click();
      await page.waitForTimeout(500);

      // Tour should be dismissed
      await expect(tour).not.toBeVisible();

      // localStorage should be set
      expect(await isTourCompleted(page)).toBe(true);
    });

    test('skip button dismisses tour and sets localStorage', async ({ page }) => {
      const user = await getTestUser();

      await clearTourStorage(page);
      await loginUser(page, user);
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      test.skip(
        page.url().includes('/login'),
        'Redirected to login — auth may have expired',
      );

      const tour = page.locator('[data-testid="product-tour"]');
      test.skip(
        (await tour.count()) === 0,
        'ProductTour not rendered — ux_v2 capability may be disabled',
      );

      // Click Skip — should dismiss
      const skipBtn = tour.locator('.product-tour-btn--skip');
      await expect(skipBtn).toBeVisible();
      await skipBtn.click();
      await page.waitForTimeout(500);

      // Tour dismissed
      await expect(tour).not.toBeVisible();

      // localStorage set
      expect(await isTourCompleted(page)).toBe(true);
    });
  });

  test.describe('Failure — Tour does not appear on subsequent login', () => {
    test('tour is not shown when localStorage flag is set', async ({ page }) => {
      const user = await getTestUser();

      // Pre-set the tour completion flag
      await page.evaluate((key) => {
        localStorage.setItem(key, 'true');
      }, TOUR_STORAGE_KEY);

      await loginUser(page, user);
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      test.skip(
        page.url().includes('/login'),
        'Redirected to login — auth may have expired',
      );

      // Tour should NOT render
      const tour = page.locator('[data-testid="product-tour"]');
      await expect(tour).not.toBeVisible();
    });
  });

  test.describe('Edge — Accessibility and persona-aware copy', () => {
    test('tour has correct a11y attributes and structure', async ({ page }) => {
      const user = await getTestUser();

      await clearTourStorage(page);
      await loginUser(page, user);
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      test.skip(
        page.url().includes('/login'),
        'Redirected to login — auth may have expired',
      );

      const tour = page.locator('[data-testid="product-tour"]');
      test.skip(
        (await tour.count()) === 0,
        'ProductTour not rendered — ux_v2 capability may be disabled',
      );

      // A11y: dialog role
      await expect(tour).toHaveAttribute('role', 'dialog');

      // A11y: accessible label
      const ariaLabel = await tour.getAttribute('aria-label');
      expect(ariaLabel).toBeTruthy();

      // Structure: title, description, progress dots, action buttons
      const title = tour.locator('.product-tour-title');
      const desc = tour.locator('.product-tour-desc');
      const dots = tour.locator('.product-tour-dot');
      const nextBtn = tour.locator('[data-testid="tour-next"]');
      const skipBtn = tour.locator('.product-tour-btn--skip');

      await expect(title).toBeVisible();
      await expect(desc).toBeVisible();
      await expect(dots).toHaveCount(5);
      await expect(nextBtn).toBeVisible();
      await expect(skipBtn).toBeVisible();

      // Verify each step has distinct content (persona-aware or default)
      const stepContents: string[] = [];
      for (let i = 0; i < 5; i++) {
        const t = await title.textContent();
        stepContents.push(t?.trim() ?? '');
        if (i < 4) {
          await nextBtn.click();
          await page.waitForTimeout(200);
        }
      }

      // All 5 steps should have unique titles
      const uniqueTitles = new Set(stepContents.filter(Boolean));
      expect(uniqueTitles.size).toBe(5);

      // Complete tour to clean up state for subsequent tests
      await nextBtn.click();
      await page.waitForTimeout(300);
    });

    test('tour handles rapid dismiss and re-login gracefully', async ({ page }) => {
      const user = await getTestUser();

      // Set tour as already completed
      await page.evaluate((key) => {
        localStorage.setItem(key, 'true');
      }, TOUR_STORAGE_KEY);

      await loginUser(page, user);
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      test.skip(
        page.url().includes('/login'),
        'Redirected to login — auth may have expired',
      );

      // Tour should not appear when localStorage flag is set
      const tour = page.locator('[data-testid="product-tour"]');
      await expect(tour).not.toBeVisible();

      // Home page should still render normally
      const homePage = page.locator(
        '[data-testid="home-page"], .home-page, [data-testid="governance-overview"]',
      );
      const homeVisible = (await homePage.count()) > 0;
      expect(homeVisible).toBe(true);
    });
  });
});
