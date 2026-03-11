/**
 * Accessibility tests using Playwright + axe-core.
 * Runs against the running app (webServer in playwright.config.ts).
 * No mocks; real axe analysis on real pages.
 *
 * Covers: login, register, password-reset, 404, 403, /public, and home (authenticated).
 * All unauthenticated routes are tested without stored auth so axe sees the real public UI.
 */
import { AxeBuilder } from '@axe-core/playwright';
import { expect } from '@playwright/test';
import { test } from '@playwright/test';

// Helper — run axe with WCAG 2 AA tags and assert no violations.
async function assertNoA11yViolations(page: import('@playwright/test').Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze();
  expect(results.violations).toEqual([]);
}

test.describe('Accessibility (axe) — public / unauthenticated pages', () => {
  test.setTimeout(60000);

  test('login page has no critical accessibility violations', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('domcontentloaded');
    await assertNoA11yViolations(page);
  });

  test('register page has no critical accessibility violations', async ({ page }) => {
    await page.goto('/register');
    await page.waitForLoadState('domcontentloaded');
    // Allow redirect to /unavailable when registration is feature-flagged off
    await page
      .locator('h1, .register-page, .unavailable-page')
      .first()
      .waitFor({ state: 'visible', timeout: 20000 })
      .catch(() => null);
    await assertNoA11yViolations(page);
  });

  test('password-reset page has no critical accessibility violations', async ({ page }) => {
    await page.goto('/password-reset');
    await page.waitForLoadState('domcontentloaded');
    await page
      .locator('h1, .password-reset-page, .unavailable-page')
      .first()
      .waitFor({ state: 'visible', timeout: 20000 })
      .catch(() => null);
    await assertNoA11yViolations(page);
  });

  test('404 page has no critical accessibility violations', async ({ page }) => {
    await page.goto('/this-route-definitely-does-not-exist-404-axe');
    await page.waitForLoadState('domcontentloaded');
    await assertNoA11yViolations(page);
  });

  test('403 page has no critical accessibility violations', async ({ page }) => {
    await page.goto('/403');
    await page.waitForLoadState('domcontentloaded');
    await assertNoA11yViolations(page);
  });

  test('public page has no critical accessibility violations', async ({ page }) => {
    await page.goto('/public');
    await page.waitForLoadState('domcontentloaded');
    await page
      .locator('h1, .public-page, #email')
      .first()
      .waitFor({ state: 'visible', timeout: 15000 })
      .catch(() => null);
    await assertNoA11yViolations(page);
  });
});

test.describe('Accessibility (axe) — authenticated pages', () => {
  test.setTimeout(90000);

  test('home page has no critical accessibility violations', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    // Wait for page to reach a stable terminal state (authenticated dashboard or landing page)
    await page
      .locator('[data-testid="home-page"], .home-page, [data-testid="landing-page"], .app-header')
      .first()
      .waitFor({ state: 'visible', timeout: 30000 })
      .catch(() => null);
    await assertNoA11yViolations(page);
  });
});
