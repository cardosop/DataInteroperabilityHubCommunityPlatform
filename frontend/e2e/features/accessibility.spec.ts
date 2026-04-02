/**
 * Accessibility tests for core authenticated pages — Phase 66 (66.3)
 *
 * Runs axe-core WCAG 2 AA analysis on /, /assets, /contracts, /datasets.
 * Asserts zero critical violations.
 */
import { AxeBuilder } from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Accessibility (axe) — core authenticated pages', () => {
  test.setTimeout(120000);

  const corePages = [
    { path: '/', name: 'Dashboard' },
    { path: '/assets', name: 'Assets' },
    { path: '/contracts', name: 'Contracts' },
    { path: '/datasets', name: 'Datasets' },
  ];

  for (const { path, name } of corePages) {
    test(`${name} page (${path}) has no critical accessibility violations`, async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, path, {
        timeout: 90000,
        contentSelector: '.app-main, .loading-spinner, .empty-state',
      });

      // Skip if redirected to login (auth not configured in this test env)
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(true, 'Auth redirect — skipping a11y check');
        return;
      }

      // Wait for page content to stabilize
      await page.waitForLoadState('networkidle').catch(() => null);
      await page.waitForTimeout(1000);

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        .analyze();

      // Filter to critical violations only
      const critical = results.violations.filter(
        (v) => v.impact === 'critical'
      );

      expect(critical).toEqual([]);
    });
  }
});
