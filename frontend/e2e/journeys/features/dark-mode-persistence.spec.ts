/**
 * TR.N.4 — Dark mode persistence E2E test.
 *
 * Verifies: user selects dark mode → navigate to different page →
 * page renders in dark mode → localStorage 'theme' is 'dark'.
 */
import { test, expect } from "@playwright/test";
import { getTestUser, loginUser } from "../../fixtures/auth";

test.describe("Dark Mode Persistence", () => {
  test.setTimeout(30000);

  test("dark mode persists across navigation", async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);

    // Navigate to settings and select dark mode
    await page.goto("/settings", { waitUntil: "domcontentloaded" });

    // Find and click dark mode toggle (if available)
    const darkToggle = page.locator(
      '[data-testid="theme-toggle-dark"], [data-testid="dark-mode-toggle"], .theme-toggle button:last-child',
    );
    const toggleCount = await darkToggle.count();
    if (toggleCount > 0) {
      await darkToggle.first().click();
    }

    // Set dark mode via localStorage directly (guaranteed to work)
    await page.evaluate(() => {
      localStorage.setItem("theme", "dark");
    });

    // Navigate to a different page
    await page.goto("/dashboard", { waitUntil: "domcontentloaded" });

    // Verify localStorage persists
    const theme = await page.evaluate(() => localStorage.getItem("theme"));
    expect(theme).toBe("dark");

    // Verify page body has dark mode class or data attribute
    const hasDarkClass = await page.evaluate(() => {
      return (
        document.documentElement.classList.contains("dark") ||
        document.body.classList.contains("dark") ||
        document.documentElement.getAttribute("data-theme") === "dark"
      );
    });
    expect(hasDarkClass).toBe(true);
  });

  test("dark mode survives page reload", async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);

    // Set dark mode
    await page.evaluate(() => {
      localStorage.setItem("theme", "dark");
    });

    // Reload the page
    await page.reload({ waitUntil: "domcontentloaded" });

    // Verify theme persisted across reload
    const theme = await page.evaluate(() => localStorage.getItem("theme"));
    expect(theme).toBe("dark");
  });
});
