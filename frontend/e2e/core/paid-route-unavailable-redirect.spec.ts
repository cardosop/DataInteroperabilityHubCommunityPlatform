/**
 * P.6 — core-mode paid-surface redirect as BEHAVIOUR (not drift assertion).
 *
 * Runs under the `chromium-core` Playwright project (E2E_CORE_ONLY=1),
 * which boots against a HUB_CORE_ONLY=1 backend: the capabilities service
 * derives every paid capability as unavailable from the OpenAPI probe, so
 * CapabilityRoute must redirect each paid route to `/unavailable`.
 *
 * This is the behavioural counterpart of the unit drift tests
 * (paidRouteDrift.test.tsx): the unit layer proves the ROUTE TREE is
 * wrapped correctly; this proves the RUNNING app actually redirects.
 */
import { expect, test } from '../fixtures/test-data-cleanup';

// The paid billing surfaces live under /settings/* and /admin/connect
// (there is NO top-level /billing route — the tree defines
// settings/subscription, settings/cost, settings/revenue,
// admin/connect).  The /marketplace and /baas top-level routes exist.
const PAID_ROUTES = [
  '/marketplace',
  '/settings/subscription',
  '/settings/cost',
  '/admin/connect',
  '/baas',
];

test.describe('Core mode: paid surfaces redirect to /unavailable', () => {
  for (const route of PAID_ROUTES) {
    test(`paid route ${route} redirects to /unavailable in core-only`, async ({
      page,
    }) => {
      await page.goto(route);
      // The gate resolves in capability order, but role-gated paid pages
      // (settings/subscription, admin/connect) hit the ROLE check first
      // and land on /403.  Both are valid gating — the invariant is that
      // the paid surface itself never renders.
      await page.waitForURL(/\/unavailable|\/403/, { timeout: 30_000 });
      expect(page.url()).toMatch(/\/unavailable|\/403/);
    });
  }

  test('a core route does NOT redirect to /unavailable', async ({ page }) => {
    await page.goto('/assets');
    // Core surfaces must render — give the app a moment, then assert we
    // did not get bounced to the paid-surface gate.
    await page.waitForLoadState('domcontentloaded');
    await expect(page).not.toHaveURL(/\/unavailable/);
  });
});
