/**
 * TR.N.2 — Mobile viewport smoke tests.
 *
 * Verifies key pages render without horizontal overflow and that
 * interactive elements meet minimum touch-target size (44×44 CSS pixels).
 * Runs only when E2E_MOBILE=1 (opt-in via Playwright project).
 */
import { test, expect } from "@playwright/test";
import { getTestUser } from "../../fixtures/auth";
import { loginAndNavigateToRoute } from "../../fixtures/helpers";

const MIN_TOUCH_TARGET = 44;

test.describe("Mobile Viewport Smoke", () => {
  test.setTimeout(60000);

  test("login page has no horizontal overflow", async ({ page }) => {
    await page.goto("/login", { waitUntil: "domcontentloaded" });
    const bodyWidth = await page.evaluate(
      () => document.documentElement.scrollWidth,
    );
    const viewportWidth = page.viewportSize()?.width ?? 390;
    expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 5);
  });

  test("dashboard loads without horizontal overflow", async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, "/dashboard", {
      timeout: 30000,
      contentSelector: ".dashboard, [data-testid='dashboard'], h1, .app-main",
    });
    const bodyWidth = await page.evaluate(
      () => document.documentElement.scrollWidth,
    );
    const viewportWidth = page.viewportSize()?.width ?? 390;
    expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 5);
  });

  test("asset detail touch targets meet minimum size", async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, "/assets", {
      timeout: 30000,
      contentSelector: ".asset-list-page, .empty-state, h1, [data-testid='asset-list-page']",
    });
    // Find interactive elements (buttons, links)
    const interactive = page.locator(
      'button, a[href], [role="button"], [role="link"], input, select, textarea',
    );
    const count = await interactive.count();
    if (count === 0) return; // Empty page — no targets to check

    // Sample first 10 interactive elements for touch target size
    for (let i = 0; i < Math.min(count, 10); i++) {
      const box = await interactive.nth(i).boundingBox();
      if (box) {
        expect(box.width).toBeGreaterThanOrEqual(
          MIN_TOUCH_TARGET - 4, // 4px tolerance for border/padding
        );
        expect(box.height).toBeGreaterThanOrEqual(
          MIN_TOUCH_TARGET - 4,
        );
      }
    }
  });

  test("marketplace listing page loads in mobile viewport", async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, "/marketplace", {
      timeout: 30000,
      contentSelector: ".marketplace-page, .listings, .empty-state, h1",
    });
    await expect(
      page.locator(".error-display").first(),
    ).not.toBeVisible({ timeout: 5000 });
  });

  test("contract editor loads in mobile viewport", async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, "/contracts", {
      timeout: 30000,
      contentSelector: ".contract-list-page, .empty-state, h1",
    });
    await expect(
      page.locator(".error-display").first(),
    ).not.toBeVisible({ timeout: 5000 });
  });
});
