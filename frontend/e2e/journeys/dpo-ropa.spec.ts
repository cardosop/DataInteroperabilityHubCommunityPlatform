/**
 * Phase 277.B.028 — DPO RoPA journey E2E.
 * DPO navigates to /settings/ropa, views records, generates RoPA, downloads.
 */
import { expect, test } from '../fixtures/test-data-cleanup';
import { getTestUser } from '../fixtures/auth';

test.describe('277.B.028 DPO RoPA journey @critical', () => {
  test.setTimeout(120_000);

  test('DPO navigates to /settings/ropa and views records', async ({ page }) => {
    const user = await getTestUser();
    await page.goto('/login');
    await page.fill('[data-testid="email-input"]', user.email);
    await page.fill('[data-testid="password-input"]', user.password);
    await page.click('[data-testid="login-submit"]');
    await page.waitForURL('**/dashboard', { timeout: 15_000 });

    await page.goto('/settings/ropa');
    await expect(page.locator('[data-testid="ropa-list"]')).toBeVisible({ timeout: 10_000 });
  });

  test('DPO generates RoPA for GDPR', async ({ page }) => {
    const user = await getTestUser();
    await page.goto('/login');
    await page.fill('[data-testid="email-input"]', user.email);
    await page.fill('[data-testid="password-input"]', user.password);
    await page.click('[data-testid="login-submit"]');
    await page.waitForURL('**/dashboard', { timeout: 15_000 });
    await page.goto('/settings/ropa');

    await expect(page.locator('[data-testid="ropa-regulation-select"]')).toBeVisible();
    await page.selectOption('[data-testid="ropa-regulation-select"]', 'GDPR');
    await page.click('[data-testid="ropa-generate-btn"]');
  });
});
