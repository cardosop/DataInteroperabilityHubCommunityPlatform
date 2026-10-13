/**
 * 276.B.106 — Billing journey for CPO persona
 *
 * Phase 276.B remediation — contract pin while the dedicated journey is
 * deferred (TICKET=PREPRO01-276B106 EXPIRES=2026-12-31). The journey
 * spec itself (CPO billing admin flows, Success/Failure/Edge) awaits the
 * billing UX sprint; until then this file pins the ACCESS contract the
 * product actually has today, so any RBAC change fails loudly and
 * prompts the journey implementation instead of drifting silently:
 *
 *   /settings/subscription   SubscriptionPage       TENANT_ADMIN | PLATFORM_ADMIN (+billing)
 *   /settings/cost           CostPage               TENANT_ADMIN | PLATFORM_ADMIN
 *   /settings/revenue        ProviderRevenuePage    TENANT_ADMIN | PLATFORM_ADMIN (+billing.stripe_connect)
 *   /settings/cost-overview  CpoCostOverviewPage    PLATFORM_ADMIN (+billing)
 *
 * The E2E CPO persona (e2e_cpo, fixture roles COMPLIANCE_OFFICER +
 * DATA_PROVIDER + TENANT_ADMIN) therefore REACHES the first three and
 * bounces to /403 on cost-overview (ProtectedRoute role mismatch).
 * Revenue content itself renders an error state for tenants without an
 * onboarded Stripe Connect provider account — route access is the
 * pinned contract there, not the data.
 *
 * Real backend only; no mocks.
 */
import { expect, test } from '@playwright/test';
import { getComplianceOfficerUser, loginUser } from '../../fixtures/auth';

test.describe('276.B.106 @deferred', () => {
  test.setTimeout(120000);

  test('CPO billing access contract while the journey is unshipped', async ({ page }) => {
    const cpo = await getComplianceOfficerUser();
    await loginUser(page, cpo);
    test.skip(page.url().includes('/login'), 'Could not authenticate');
    if (page.url().includes('/login')) {
      return;
    }

    // TENANT_ADMIN-scoped surfaces are reachable for the CPO persona —
    // the URL must stay on the route (ProtectedRoute must NOT bounce).
    const reachable = ['/settings/subscription', '/settings/cost', '/settings/revenue'] as const;
    for (const route of reachable) {
      await page.goto(route);
      await page.waitForTimeout(1500);
      expect(
        page.url().includes(route) && !page.url().includes('/403'),
        `CPO no longer reaches ${route} — RBAC changed; implement the billing journey (PREPRO01-276B106)`
      ).toBe(true);
    }

    // Content renders on the surfaces that have tenant-level data.
    await page.goto('/settings/subscription');
    await expect(page.locator('.subscription-page').first()).toBeVisible({ timeout: 30000 });
    await page.goto('/settings/cost');
    await expect(page.locator('[data-testid="cost-page"]').first()).toBeVisible({ timeout: 30000 });

    // PLATFORM_ADMIN-only cost overview stays closed to the CPO.
    await page.goto('/settings/cost-overview');
    await page.waitForURL(/\/(403|unavailable)/, { timeout: 20000 });
    expect(
      page.url(),
      'CPO reached /settings/cost-overview — RBAC changed; implement the billing journey (PREPRO01-276B106)'
    ).toContain('/403');
  });
});
