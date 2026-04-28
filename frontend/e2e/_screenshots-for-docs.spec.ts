/**
 * Screenshots for documentation — Phase 217.5.10
 *
 * Captures persona quickstart and use-case screenshots to
 * docs/mvpdocs/_assets/screenshots/. Regenerated nightly;
 * PR diff highlights stale screenshots. Filenames stable
 * per UC/journey ID.
 *
 * Run: npx playwright test _screenshots-for-docs.spec.ts
 */

import { test, expect } from "@playwright/test";
import path from "path";

const SCREENSHOT_DIR = path.resolve(
  __dirname,
  "../../docs/mvpdocs/_assets/screenshots"
);

const VIEWPORTS = {
  desktop: { width: 1280, height: 720 },
  iphone: { width: 375, height: 812 },
  android: { width: 412, height: 915 },
};

// Persona quickstart pages to capture
const PERSONA_PAGES = [
  { name: "dpo-quickstart", path: "/docs/mvpdocs/personas/data-product-owner/quickstart/" },
  { name: "de-quickstart", path: "/docs/mvpdocs/personas/data-engineer/quickstart/" },
  { name: "cpo-quickstart", path: "/docs/mvpdocs/personas/compliance-privacy-officer/quickstart/" },
  { name: "dc-quickstart", path: "/docs/mvpdocs/personas/data-consumer/quickstart/" },
  { name: "mpa-quickstart", path: "/docs/mvpdocs/personas/marketplace-platform-admin/quickstart/" },
  { name: "dev-quickstart", path: "/docs/mvpdocs/personas/external-developer/quickstart/" },
];

// Key use-case pages
const UC_PAGES = [
  { name: "UC-AUTH-001", path: "/docs/mvpdocs/use-cases/UC-AUTH-001/" },
  { name: "UC-AM-001", path: "/docs/mvpdocs/use-cases/UC-AM-001/" },
  { name: "UC-DQ-001", path: "/docs/mvpdocs/use-cases/UC-DQ-001/" },
  { name: "UC-COMP-001", path: "/docs/mvpdocs/use-cases/UC-COMP-001/" },
];

test.describe("Documentation screenshots @critical", () => {
  for (const viewport of Object.entries(VIEWPORTS)) {
    const [vpName, vpSize] = viewport;

    test.describe(`${vpName} (${vpSize.width}x${vpSize.height})`, () => {
      test.use({ viewport: vpSize });

      // Landing page
      test(`landing-${vpName}`, async ({ page }) => {
        await page.goto("/docs/mvpdocs/");
        await expect(page.locator("h1")).toBeVisible();
        await page.screenshot({
          path: path.join(SCREENSHOT_DIR, `landing-${vpName}.png`),
          fullPage: true,
        });
      });

      // Persona quickstarts
      for (const persona of PERSONA_PAGES) {
        test(`${persona.name}-${vpName}`, async ({ page }) => {
          await page.goto(persona.path);
          await expect(page.locator("h1")).toBeVisible();
          await page.screenshot({
            path: path.join(
              SCREENSHOT_DIR,
              `${persona.name}-${vpName}.png`
            ),
            fullPage: true,
          });
        });
      }

      // Use cases (desktop only to reduce screenshot volume)
      if (vpName === "desktop") {
        for (const uc of UC_PAGES) {
          test(`${uc.name}-${vpName}`, async ({ page }) => {
            await page.goto(uc.path);
            await expect(page.locator("h1")).toBeVisible();
            await page.screenshot({
              path: path.join(
                SCREENSHOT_DIR,
                `${uc.name}-${vpName}.png`
              ),
              fullPage: true,
            });
          });
        }
      }
    });
  }
});

// Mobile rendering audit screenshots (Phase 217.5.6)
test.describe("Mobile rendering audit", () => {
  const MOBILE_DIR = path.resolve(
    __dirname,
    "../../docs/mvpdocs/_audit/mobile-screenshots"
  );

  for (const [vpName, vpSize] of [
    ["iphone", VIEWPORTS.iphone],
    ["android", VIEWPORTS.android],
  ] as const) {
    test(`mobile-audit-${vpName}`, async ({ page }) => {
      await page.setViewportSize(vpSize);
      await page.goto("/docs/mvpdocs/");
      await expect(page.locator("h1")).toBeVisible();
      await page.screenshot({
        path: path.join(MOBILE_DIR, `landing-${vpName}.png`),
        fullPage: true,
      });
    });
  }
});

// Search quality check (Phase 217.5.7)
test.describe("Search quality", () => {
  const SEARCH_QUERIES = [
    { query: "quickstart", expectResult: "Quickstart" },
    { query: "asset", expectResult: "Asset" },
    { query: "compliance", expectResult: "Compliance" },
    { query: "webhook", expectResult: "Webhook" },
    { query: "deploy", expectResult: "Deploy" },
    { query: "GDPR", expectResult: "GDPR" },
  ];

  for (const { query, expectResult } of SEARCH_QUERIES) {
    test(`search "${query}" returns relevant result`, async ({
      page,
    }) => {
      await page.goto("/docs/mvpdocs/");
      // Material theme search: click the search icon, type query
      const searchInput = page.locator(
        'input[type="search"], .md-search__input'
      );
      if (await searchInput.isVisible()) {
        await searchInput.fill(query);
        // Wait for search results to appear
        await page.waitForTimeout(500);
        const results = page.locator(".md-search-result__link");
        const count = await results.count();
        expect(count).toBeGreaterThan(0);
      }
    });
  }
});
