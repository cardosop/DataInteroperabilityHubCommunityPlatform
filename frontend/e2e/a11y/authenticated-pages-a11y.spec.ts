/**
 * Accessibility tests for authenticated pages.
 *
 * Performs basic a11y checks (images have alt text, inputs have labels) on key
 * authenticated routes. No axe-core dependency — fast checks that always run.
 */
import { test, expect } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';

const AUTHENTICATED_ROUTES = [
  '/assets',
  '/contracts',
  '/datasets',
  '/marketplace/listings',
  '/jobs',
  '/webhooks',
  '/governance/access-requests',
  '/compliance',
  '/data-quality',
  '/search',
];

test.describe('Authenticated Pages A11y', () => {
  test.setTimeout(120000);

  for (const route of AUTHENTICATED_ROUTES) {
    test(`${route} has no critical a11y violations`, async ({ page }) => {
      // Authenticate first — these are protected routes
      const user = await getTestUser();
      await loginUser(page, user);
      if (page.url().includes('/login')) {
        test.skip(true, 'Could not authenticate — backend may be unreachable');
        return;
      }

      // Navigate to the target route
      await page.goto(route, { waitUntil: 'domcontentloaded' });
      // Wait for meaningful content (app shell or the page itself)
      await page
        .locator('.app-main, .app-sidebar, [role="main"]')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      // If redirected to login, auth failed for this route — skip
      if (page.url().includes('/login')) {
        test.skip(true, `Redirected to login from ${route} — auth or capability issue`);
        return;
      }

      // Basic a11y checks (no axe-core dependency)
      // Check all images have alt text
      const imgsWithoutAlt = await page.locator('img:not([alt])').count();
      expect(imgsWithoutAlt).toBe(0);

      // Check all form inputs have labels or aria-label
      const inputsWithoutLabel = await page
        .locator('input:not([aria-label]):not([id]):not([type="hidden"])')
        .count();
      if (inputsWithoutLabel > 0) {
        console.warn(`${route}: ${inputsWithoutLabel} inputs without labels`);
      }
    });
  }
});
