/**
 * E2E: Meshant Layout (Phase 29.0.5)
 * Asserts .app-main max-width 1200px, sidebar 240px, content centered on wide viewport.
 */
import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';

test.describe('Meshant Layout (Phase 29.0)', () => {
  test.beforeEach(async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);
  });

  test('.app-main has max-width 1200px (computed style)', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.app-main', { state: 'visible', timeout: 15000 });

    const maxWidth = await page.locator('.app-main').evaluate((el) => {
      const style = window.getComputedStyle(el);
      return style.maxWidth;
    });
    expect(maxWidth).toBe('1200px');
  });

  test('sidebar has width 240px', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.app-sidebar', { state: 'visible', timeout: 15000 });

    const width = await page.locator('.app-sidebar').evaluate((el) => {
      const style = window.getComputedStyle(el);
      return style.width;
    });
    expect(width).toBe('240px');
  });

  test('content is centered on wide viewport', async ({ page }) => {
    await page.setViewportSize({ width: 1600, height: 900 });
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.app-main', { state: 'visible', timeout: 15000 });

    const { marginLeft, marginRight, width } = await page.locator('.app-main').evaluate((el) => {
      const style = window.getComputedStyle(el);
      return {
        marginLeft: style.marginLeft,
        marginRight: style.marginRight,
        width: style.width,
      };
    });
    // With margin: 0 auto in flex, extra space distributes equally; margins equal when centered
    expect(marginLeft).toBe(marginRight);
    expect(parseInt(width, 10)).toBeLessThanOrEqual(1200);
  });
});
