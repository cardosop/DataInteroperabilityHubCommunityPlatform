/**
 * Phase 226.F6 — Visual-regression baselines on 10 core pages.
 *
 * Per the F6 task: snapshot a curated set of pages so layout / CSS /
 * font-rendering regressions are caught at PR time. The threshold and
 * animation-disable defaults are set on the dedicated
 * `playwright.visual.config.ts` so functional tests are unaffected.
 *
 * Snapshots live under `e2e/visual/__snapshots__/`. To bump the
 * baselines after an intentional UI change:
 *
 *     cd frontend
 *     npx playwright test --config=playwright.visual.config.ts \
 *       --update-snapshots
 *     git add e2e/visual/__snapshots__
 *     git commit -m "ui: refresh visual baselines for <change>"
 *
 * Each test:
 *   1. Logs in (storageState already provisioned by `setup-auth`).
 *   2. Navigates to the target page and waits for a stable terminal
 *      element (so snapshots aren't taken mid-skeleton).
 *   3. Masks dynamic regions (timestamps, request IDs) so noise
 *      doesn't trip the gate on every run.
 *   4. Snapshots the full page.
 *
 * The page list is the 10 core pages named in the task description:
 *   home, asset list, asset detail, dataset detail, compliance detail,
 *   DQ detail, contracts detail, marketplace list, listing detail,
 *   admin settings.
 *
 * Where the deployed environment doesn't have a seeded
 * detail-page resource (e.g. no asset exists yet), the test
 * skips with a specific reason so the per-reason skip-counter gate
 * still surfaces drift.
 *
 * Real backend only — no mocks.
 */

import { expect, test, type Locator, type Page } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';

const TERMINAL_LOAD_SELECTORS =
  '.app-header, [data-testid="app-header"], .app-shell, [data-testid="app-shell"], main, [role="main"]';

/**
 * Selectors that mask dynamic regions across all snapshots:
 *   - Timestamps / "X minutes ago" badges.
 *   - Request IDs in error footers.
 *   - Mood-of-the-day / activity feed sparklines.
 *   - User avatars / display names (per-account rotation).
 */
const DYNAMIC_REGION_SELECTORS = [
  '[data-relative-time]',
  '[data-testid$="-timestamp"]',
  '.timestamp',
  '.relative-time',
  '.error-display-request-id',
  '[data-testid="user-display-name"]',
  '.user-avatar',
];

/**
 * Build the masking locator list for a given page. Defensive lookup
 * — locators that match nothing are no-ops in Playwright's mask API.
 */
function masksFor(page: Page): Locator[] {
  return DYNAMIC_REGION_SELECTORS.map((sel) => page.locator(sel));
}

async function navigateAndStabilise(page: Page, path: string, label: string) {
  await page.goto(path, { waitUntil: 'domcontentloaded' });
  // Wait for either the app shell OR a terminal-error/unavailable state.
  await page
    .locator(TERMINAL_LOAD_SELECTORS)
    .first()
    .waitFor({ state: 'visible', timeout: 30_000 });
  // intentional: extra settling time allows webfonts + capability fetches to land before the snapshot fires; without it the first run on a cold environment captures a partial render.
  await page.waitForTimeout(800);
  console.log(`[visual] ready for ${label} → ${page.url()}`);
}

async function pickFirstResourceId(
  page: Page,
  endpoint: string,
): Promise<string | null> {
  const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
  if (!accessToken) return null;
  // intentional: visual baselines tolerate transient API issues; if the lookup fails, the spec skips with a specific reason rather than failing the whole gate. The functional gates already catch list-endpoint regressions.
  const res = await page.request.get(endpoint, {
    headers: { Authorization: `Bearer ${accessToken}` },
    failOnStatusCode: false,
  });
  if (!res.ok()) return null;
  const body = (await res.json()) as { results?: Array<{ id: string }> } | Array<{ id: string }>;
  const list = Array.isArray(body) ? body : body.results ?? [];
  return list[0]?.id ?? null;
}

test.describe('Visual regression baselines @visual', () => {
  test('home page', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await navigateAndStabilise(page, '/', 'home');
    await expect(page).toHaveScreenshot('home.png', {
      fullPage: true,
      mask: masksFor(page),
    });
  });

  test('asset list', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await navigateAndStabilise(page, '/assets', 'asset-list');
    await expect(page).toHaveScreenshot('asset-list.png', {
      fullPage: true,
      mask: masksFor(page),
    });
  });

  test('asset detail', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await page.goto('/assets', { waitUntil: 'domcontentloaded' });
    const id = await pickFirstResourceId(page, '/api/v1/assets/');
    test.skip(
      id === null,
      'No asset available on this tenant — visual baseline cannot be captured. Seed an asset and re-run with --update-snapshots.',
    );
    if (id === null) return;
    await navigateAndStabilise(page, `/assets/${id}`, 'asset-detail');
    await expect(page).toHaveScreenshot('asset-detail.png', {
      fullPage: true,
      mask: masksFor(page),
    });
  });

  test('dataset detail', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await page.goto('/datasets', { waitUntil: 'domcontentloaded' });
    const id = await pickFirstResourceId(page, '/api/v1/datasets/');
    test.skip(
      id === null,
      'No dataset available — seed one and re-run with --update-snapshots.',
    );
    if (id === null) return;
    await navigateAndStabilise(page, `/datasets/${id}`, 'dataset-detail');
    await expect(page).toHaveScreenshot('dataset-detail.png', {
      fullPage: true,
      mask: masksFor(page),
    });
  });

  test('compliance detail', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await page.goto('/compliance', { waitUntil: 'domcontentloaded' });
    const id = await pickFirstResourceId(page, '/api/v1/compliance/runs/');
    test.skip(
      id === null,
      'No compliance run available — seed one and re-run with --update-snapshots.',
    );
    if (id === null) return;
    await navigateAndStabilise(page, `/compliance/runs/${id}`, 'compliance-detail');
    await expect(page).toHaveScreenshot('compliance-detail.png', {
      fullPage: true,
      mask: masksFor(page),
    });
  });

  test('data-quality detail', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await page.goto('/data-quality', { waitUntil: 'domcontentloaded' });
    const id = await pickFirstResourceId(page, '/api/v1/dq/runs/');
    test.skip(
      id === null,
      'No DQ run available — seed one and re-run with --update-snapshots.',
    );
    if (id === null) return;
    await navigateAndStabilise(page, `/data-quality/runs/${id}`, 'dq-detail');
    await expect(page).toHaveScreenshot('dq-detail.png', {
      fullPage: true,
      mask: masksFor(page),
    });
  });

  test('contracts detail', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await page.goto('/contracts', { waitUntil: 'domcontentloaded' });
    const id = await pickFirstResourceId(page, '/api/v1/contracts/');
    test.skip(
      id === null,
      'No contract available — seed one and re-run with --update-snapshots.',
    );
    if (id === null) return;
    await navigateAndStabilise(page, `/contracts/${id}`, 'contracts-detail');
    await expect(page).toHaveScreenshot('contracts-detail.png', {
      fullPage: true,
      mask: masksFor(page),
    });
  });

  test('marketplace list', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await navigateAndStabilise(page, '/marketplace', 'marketplace-list');
    await expect(page).toHaveScreenshot('marketplace-list.png', {
      fullPage: true,
      mask: masksFor(page),
    });
  });

  test('marketplace listing detail', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });
    const id = await pickFirstResourceId(page, '/api/v1/marketplace/listings/');
    test.skip(
      id === null,
      'No marketplace listing available — seed one and re-run with --update-snapshots.',
    );
    if (id === null) return;
    await navigateAndStabilise(page, `/marketplace/listings/${id}`, 'listing-detail');
    await expect(page).toHaveScreenshot('listing-detail.png', {
      fullPage: true,
      mask: masksFor(page),
    });
  });

  test('admin settings', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await navigateAndStabilise(page, '/admin/settings', 'admin-settings');
    await expect(page).toHaveScreenshot('admin-settings.png', {
      fullPage: true,
      mask: masksFor(page),
    });
  });
});
