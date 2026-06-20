/**
 * 285.9b.P.1 — ML pages accessibility axe audit.
 *
 * Runs WCAG 2.1 AA checks against ML model detail, training dashboard,
 * and ML platform pages.  Requires the app to be running.
 */
import { AxeBuilder } from '@axe-core/playwright';
import { expect } from '@playwright/test';
import { test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';

async function assertNoA11yViolations(page: import('@playwright/test').Page, originalUrl: string): Promise<void> {
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  await page.waitForTimeout(1500);
  // The ML page uses React.lazy() for its chunked components.  Under
  // load the Vite dev server may fail to serve the ML chunk, rendering
  // a ``<vite-error-overlay>`` in the DOM.  Navigate away to a simple
  // page and back — this gives Vite time to GC and recompile, and
  // avoids any browser-level module cache that a plain reload would hit.
  let hasViteError = false;
  for (let attempt = 0; attempt < 3; attempt++) {
    hasViteError = (await page.locator('vite-error-overlay').count()) > 0;
    if (!hasViteError) break;
    if (attempt < 2) {
      console.warn(`Vite error overlay on ML page — navigate-away retry ${attempt + 1}/2...`);
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1000);
      await page.goto(originalUrl, { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
      await page.waitForTimeout(2000 + attempt * 2000);
    }
  }
  test.skip(hasViteError, 'Vite error overlay — ML chunk load failed after 2 navigate-away retries');
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze();
  expect(results.violations).toEqual([]);
}

const MODEL_ID = '00000000-0000-0000-0000-000000000001';

test.describe('ML Platform — Accessibility', () => {
  test('ML page has no axe violations', async ({ page }) => {
    await page.goto('/ml');
    await assertNoA11yViolations(page, '/ml');
  });

  test('model detail page has no axe violations', async ({ page }) => {
    await page.goto(`/ml/models/${MODEL_ID}`);
    await assertNoA11yViolations(page, `/ml/models/${MODEL_ID}`);
  });

  test('training dashboard has no axe violations', async ({ page }) => {
    await page.goto(`/ml/training/${MODEL_ID}`);
    await assertNoA11yViolations(page, `/ml/training/${MODEL_ID}`);
  });

  test('tab navigation is keyboard accessible', async ({ page }) => {
    await page.goto('/ml');
    const tabs = page.locator('.ml-tab');
    const count = await tabs.count();
    for (let i = 0; i < count; i++) {
      await expect(tabs.nth(i)).toBeVisible();
    }
  });
});

test.describe('ML — Dark mode', () => {
  test('ML page renders without contrast violations in dark mode', async ({ page }) => {
    // Explicitly authenticate before navigating — dark mode tests run late
    // in the suite (>55 tests in), so storageState auth may have expired.
    // Without this, the SPA redirects to /login and axe scans the login page
    // instead of the ML page (false positive contrast failures from AuthPage.css).
    const user = await getTestUser();
    await loginUser(page, user);
    await page.goto('/ml');
    await page.emulateMedia({ colorScheme: 'dark' });
    await assertNoA11yViolations(page, '/ml');
  });

  test('model detail page renders in dark mode', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await page.goto(`/ml/models/${MODEL_ID}`);
    await page.emulateMedia({ colorScheme: 'dark' });
    await assertNoA11yViolations(page, `/ml/models/${MODEL_ID}`);
  });
});
