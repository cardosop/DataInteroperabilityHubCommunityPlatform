/**
 * 283.3.1.3 — G6 a11y: axe scan on ConsentDashboard.
 *
 * Runs against the real ConsentDashboard page with an authenticated
 * TENANT_ADMIN user. Uses axe-core via @axe-core/playwright to assert
 * no WCAG 2.1 AA violations.
 */
import { AxeBuilder } from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { loginUser, getTenantAdminUser } from '../fixtures/auth';

async function assertNoA11yViolations(page: import('@playwright/test').Page): Promise<void> {
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze();
  expect(results.violations).toEqual([]);
}

test.describe('A11y axe coverage — ConsentDashboard @a11y @consent', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    const user = await getTenantAdminUser();
    await loginUser(page, user);
  });

  test('consent dashboard page has no critical a11y violations', async ({ page }) => {
    await page.goto('/governance/consent-dashboard', { waitUntil: 'domcontentloaded' });
    await assertNoA11yViolations(page);
  });
});
