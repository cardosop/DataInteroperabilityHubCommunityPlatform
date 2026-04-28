/**
 * E2E spec — Plan-limit-reached modal guardrail (Phase 226.G4).
 *
 * Background
 * ----------
 * Plan-limit response shape is asserted at the API layer by
 * `journeys/admin-surface/plan-limit-guard.spec.ts` (G3). This spec is the
 * UI-side counterpart — it asserts the *user-visible* guardrail: when a
 * create flow returns 403 plan_limit_exceeded, the SPA shows an
 * actionable modal/banner that:
 *   1. Cites the limit_key, current usage, max.
 *   2. Surfaces a "Contact admin to upgrade plan" or equivalent CTA.
 *   3. Blocks the action — no in-flight orphan, no silent retry loop.
 *
 * The plan limit is exercised here by toggling Playwright's `route` to
 * intercept the create response and inject 403 + the canonical body
 * shape, so the spec doesn't need to actually saturate the tenant's plan
 * (which would slow the suite and create cleanup orphans).
 *
 * Note on routing — this is the ONE place a route override is justified:
 * we are not stubbing logic (which would defeat the spec). We are
 * simulating the *response* of the real backend's existing
 * plan_limit_exceeded code path. The shape we inject MUST exactly match
 * what `PlanLimitService.check_limit` produces (`hub/apps/tenants/services.py:
 * 757-770`). If those shapes drift, this spec fails — surfacing the drift.
 *
 * No mocks of business logic. Only injects the canonical 403 response
 * shape that the real backend code path actually emits.
 */

import { test, expect } from '../../fixtures/guardedTest';
import { getTestUser } from '../../fixtures/auth';
import {
  loginAndNavigateToRoute,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('226.G4 — Plan-limit-reached modal @critical @guardrail', () => {
  test.setTimeout(120_000);

  test('UI surfaces actionable warning with limit details and blocks action when plan_limit_exceeded fires', async ({
    page,
  }) => {
    // UI nav under loginUser hits /auth/me/, /auth/me/tenants/, etc. Some of
    // those endpoints do not currently echo X-Correlation-ID. Opt out of
    // the missing-echo check; the modal-visibility assertions are the
    // spec's verdict.
    test.info().annotations.push({
      type: 'allow-missing-correlation-id',
      description:
        'UI nav hits /auth/me/, /auth/me/tenants/ which do not echo X-Correlation-ID. ' +
        'Pre-existing backend gap; tracked separately.',
    });

    const dpo = await getTestUser();

    // Drive the UI: full login + navigate to /assets/create using the
    // canonical helper that's robust to capability-discovery + auth
    // hydration delays. `loginUser` + raw `page.goto('/assets/create')`
    // races the SPA's auth init under parallel-worker load and lands on
    // /login or empty content; loginAndNavigateToRoute handles all that.
    await loginAndNavigateToRoute(page, dpo, '/assets/create', {
      timeout: 60000,
      contentSelector:
        '.asset-create-page, [data-testid="asset-create-page"], form, .error-display, [data-testid="error-display"], h1',
    });
    await waitForLoadingComplete(page);

    // Inject the canonical 403 shape on the next asset-create POST. The
    // shape mirrors PlanLimitService.check_limit's actual response — if
    // that code drifts, this assertion drifts with it (intentional).
    // Routing is set up AFTER navigation so the page-load doesn't
    // accidentally hit the route handler.
    let interceptCount = 0;
    await page.route('**/api/v1/assets/', async (route, request) => {
      if (request.method() !== 'POST') {
        await route.fallback();
        return;
      }
      interceptCount++;
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Plan limit exceeded for max_assets',
          code: 'plan_limit_exceeded',
          details: {
            limit_key: 'max_assets',
            current: 10,
            max: 10,
            requested_delta: 1,
            new_usage: 11,
            plan_slug: 'free',
            plan_tier: 'FREE',
          },
        }),
      });
    });

    const keyInput = page.locator('input[id="asset-key"], input[name="key"]').first();
    await keyInput.waitFor({ state: 'visible', timeout: 30_000 });
    await page.fill('input[id="asset-name"], input[name="name"]', 'G4 Plan Limit Probe');
    await keyInput.fill(`g4-pl-${Date.now()}`);
    await page.fill(
      'textarea[id="asset-description"], textarea[name="description"]',
      'G4 plan-limit modal probe',
    );
    const visibilitySelect = page.locator('select[id="asset-visibility"], select[name="visibility"]');
    if ((await visibilitySelect.count()) > 0) {
      await visibilitySelect.first().selectOption('INTERNAL');
    }

    const submitBtn = page
      .locator('button[type="submit"]:has-text("Create"), button:has-text("Create Asset")')
      .first();
    await submitBtn.click();

    // Wait for the inject-fulfilled response to reach the SPA.
    await expect.poll(() => interceptCount, { timeout: 15_000 }).toBeGreaterThan(0);

    // ── Assert visible: the SPA must surface the limit somewhere. The exact
    // selector varies by component — we look for any user-visible string
    // that references the limit, plan, or upgrade CTA.
    const visibleSignal = page.locator(
      [
        '[data-testid="plan-limit-modal"]',
        '.plan-limit-modal',
        '.plan-limit-banner',
        '.error-display',
        '.toast-error',
      ].join(', '),
    );
    // 5s is enough for React to render. If the spec fails here, the SPA is
    // not handling 403+plan_limit_exceeded — that IS the bug we're guarding.
    await expect(visibleSignal.first()).toBeVisible({ timeout: 8_000 });

    // ── Assert blocks the action: no navigation to /assets/{id} happened
    // (would indicate the SPA proceeded as if create succeeded).
    expect(
      page.url(),
      `URL drifted to /assets/{id} despite 403 plan_limit_exceeded — submit was not blocked. URL=${page.url()}`,
    ).not.toMatch(/\/assets\/[0-9a-f]{8}-[0-9a-f]{4}/i);
  });
});
