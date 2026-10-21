/**
 * E2E: Meshant Layout (Phase 29.0.5)
 *
 * Verifies layout behaviour visible to users:
 *   - Content area is bounded and doesn't overflow on wide viewports
 *   - Sidebar is navigable and visible alongside the main content
 *   - Content is centered on a wide viewport (visual centering)
 *
 * NOTE: Exact pixel values (1200px, 240px) were removed. They are implementation details
 * that belong in CSS snapshot/unit tests, not E2E tests. Hardcoded values create fragile
 * test failures on legitimate redesigns and add no user-experience signal.
 * If you need to pin the exact design-token values, use Storybook visual tests or a CSS
 * regression tool (e.g. Percy, Chromatic) instead.
 */
import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';

test.describe('Meshant Layout (Phase 29.0)', () => {
  test.beforeEach(async ({ page }) => {
    const testUser = await getTestUser();
    // Retry once: late-batch Vite GC pauses can cause the first login to
    // time out on the app-shell wait.  A second attempt with fresh JS
    // context usually succeeds.
    let lastErr: unknown;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        await loginUser(page, testUser);
        await page.locator('.app-sidebar').waitFor({ state: 'visible', timeout: 15_000 });
        return;
      } catch (err) {
        lastErr = err;
        if (attempt === 0) {
          await page.context().clearCookies().catch(() => {});
          await page.evaluate(() => localStorage.clear()).catch(() => {});
          await page.goto('/login', { waitUntil: 'domcontentloaded' });
          await page.waitForTimeout(2000);
        }
      }
    }
    throw lastErr ?? new Error('meshant-layout beforeEach: loginUser failed after 2 attempts');
  });

  test('.app-main, [data-testid="app-main"] is bounded and does not overflow on a wide viewport', async ({ page }) => {
    // Behavioral assertion: the content area must not be wider than the viewport,
    // and must have a max-width applied (not stretch infinitely).
    // NOTE: loginUser in beforeEach already navigated to '/' with the app shell visible.
    // Do NOT call page.goto('/') again — a full reload re-initializes auth, which under
    // parallel E2E load takes 60-120s and causes timeout failures.
    await page.setViewportSize({ width: 1920, height: 900 });
    // CSS reflows automatically on viewport change; wait briefly for layout to settle
    await page.waitForTimeout(500);
    await page.waitForSelector('.app-main, [data-testid="app-main"]', { state: 'visible', timeout: 30000 });

    const { mainWidth, viewportWidth, hasMaxWidth } = await page.locator('.app-main, [data-testid="app-main"]').first().evaluate((el) => {
      const style = window.getComputedStyle(el);
      return {
        mainWidth: el.getBoundingClientRect().width,
        viewportWidth: window.innerWidth,
        // A max-width is set if the computed value is not 'none'
        hasMaxWidth: style.maxWidth !== 'none' && style.maxWidth !== '',
      };
    });
    // Content must not span the full viewport (must be bounded by a max-width)
    expect(hasMaxWidth).toBe(true);
    // Content width must be less than the full 1920px viewport
    expect(mainWidth).toBeLessThan(viewportWidth);
    // Practical upper bound: content area should be at most 1400px on any design
    expect(mainWidth).toBeLessThanOrEqual(1400);
  });

  test('sidebar is visible and navigable alongside main content', async ({ page }) => {
    // Behavioral assertion: the sidebar and main content must coexist (not overlap or hide each other).
    // loginUser in beforeEach already navigated to '/' — app shell should be visible.
    await page.waitForSelector('.app-sidebar', { state: 'visible', timeout: 30000 });
    await page.waitForSelector('.app-main, [data-testid="app-main"]', { state: 'visible', timeout: 30000 });

    const sidebarBox = await page.locator('.app-sidebar').boundingBox();
    const mainBox = await page.locator('.app-main, [data-testid="app-main"]').first().boundingBox();

    expect(sidebarBox).not.toBeNull();
    expect(mainBox).not.toBeNull();

    // Sidebar must be visible (non-zero dimensions)
    expect(sidebarBox!.width).toBeGreaterThan(0);
    expect(sidebarBox!.height).toBeGreaterThan(0);

    // Sidebar and main content must not overlap horizontally (sidebar is left of main)
    expect(sidebarBox!.x + sidebarBox!.width).toBeLessThanOrEqual(mainBox!.x + 2); // 2px tolerance

    // Sidebar must have at least one navigable link
    const navLinks = page.locator('.app-sidebar .nav-link');
    await expect(navLinks.first()).toBeVisible({ timeout: 5000 });
    expect(await navLinks.count()).toBeGreaterThan(0);
  });

  test('content is centered on wide viewport', async ({ page }) => {
    // Behavioral assertion: on a wide viewport the main content area must be
    // horizontally centered (equal space on both sides), not left-aligned.
    // loginUser in beforeEach already navigated to '/' — no reload needed.
    await page.setViewportSize({ width: 1600, height: 900 });
    await page.waitForTimeout(500); // CSS reflow after viewport change
    await page.waitForSelector('.app-main, [data-testid="app-main"]', { state: 'visible', timeout: 30000 });

    const { marginLeft, marginRight, mainWidth, viewportWidth } = await page
      .locator('.app-main, [data-testid="app-main"]').first()
      .evaluate((el) => {
        const style = window.getComputedStyle(el);
        return {
          marginLeft: parseFloat(style.marginLeft),
          marginRight: parseFloat(style.marginRight),
          mainWidth: el.getBoundingClientRect().width,
          viewportWidth: window.innerWidth,
        };
      });

    // Content must be narrower than viewport (otherwise centering is impossible to verify)
    expect(mainWidth).toBeLessThan(viewportWidth);
    // Margins must be approximately equal (centered layout) — allow 8px tolerance for sub-pixel
    expect(Math.abs(marginLeft - marginRight)).toBeLessThanOrEqual(8);
  });
});
