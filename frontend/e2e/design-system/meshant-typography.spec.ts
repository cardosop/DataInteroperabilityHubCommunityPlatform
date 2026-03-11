/**
 * E2E: Meshant Typography (Phase 29.0.6)
 * Asserts body font-family includes Inter; key headings use design tokens (smoke only).
 */
import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';

test.describe('Meshant Typography (Phase 29.0)', () => {
  test.beforeEach(async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);
  });

  test('body font-family includes Inter', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });

    const fontFamily = await page.locator('body').evaluate((el) => {
      const style = window.getComputedStyle(el);
      return style.fontFamily;
    });
    expect(fontFamily).toContain('Inter');
  });

  test('key headings use design tokens (smoke)', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.app-main, h1', { state: 'visible', timeout: 15000 });

    const h1 = page.locator('h1').first();
    await expect(h1).toBeVisible();
    const fontFamily = await h1.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return style.fontFamily;
    });
    expect(fontFamily).toContain('Inter');
  });
});
