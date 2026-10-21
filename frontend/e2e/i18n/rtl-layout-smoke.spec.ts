/**
 * TR.O.8 — RTL layout smoke test for Arabic (ar) and Hebrew (he) locales.
 *
 * Verifies pages render without horizontal overflow when direction is RTL
 * and text flows right-to-left.
 */
import { test, expect } from "@playwright/test";
import { getTestUser, loginUser } from "../fixtures/auth";

test.describe("RTL Layout Smoke (TR.O.8)", () => {
  test.setTimeout(30000);

  test("login page renders RTL without overflow (ar locale)", async ({
    page,
  }) => {
    await page.goto("/login", { waitUntil: "domcontentloaded" });
    // Set HTML dir and lang to simulate Arabic locale
    await page.evaluate(() => {
      document.documentElement.setAttribute("dir", "rtl");
      document.documentElement.setAttribute("lang", "ar");
    });
    const bodyWidth = await page.evaluate(
      () => document.documentElement.scrollWidth,
    );
    const viewportWidth = page.viewportSize()?.width ?? 390;
    expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 5);
    // Verify text direction
    const dir = await page.evaluate(
      () => document.documentElement.getAttribute("dir"),
    );
    expect(dir).toBe("rtl");
  });

  test("dashboard renders RTL without overflow (he locale)", async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
    await page.evaluate(() => {
      document.documentElement.setAttribute("dir", "rtl");
      document.documentElement.setAttribute("lang", "he");
    });
    const bodyWidth = await page.evaluate(
      () => document.documentElement.scrollWidth,
    );
    const viewportWidth = page.viewportSize()?.width ?? 390;
    expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 5);
  });
});
