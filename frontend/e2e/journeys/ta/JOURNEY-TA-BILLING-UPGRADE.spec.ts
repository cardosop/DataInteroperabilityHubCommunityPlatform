/**
 * E2E Test: JOURNEY-TA-BILLING-UPGRADE — Tenant Admin upgrades subscription plan
 *
 * Journey: A Tenant Admin opens billing, selects a different plan, and the
 * subscription transitions to the new plan with the correct audit trail.
 * Covers the plan-upgrade business logic end-to-end.
 *
 * Priority: Critical
 * Use Case: UC-BILL-002 (Billing Upgrade — net-new in Phase 217.1.4,
 *           critical-id-listed in docs/CRITICAL_UC_JOURNEY_IDS.yaml:52)
 * Tracked under: Phase 226.D3
 *
 * What this spec proves today
 * ---------------------------
 * Without the Stripe secret key wired into the staging backend
 * (externalSecrets.stripe.enabled is `false` in helm/values.staging.yaml;
 * STRIPE_SECRET_KEY is not in the repo's gh secrets either), the backend
 * `SubscriptionService.update_subscription` takes the non-Stripe path:
 *
 *   1. Validates the plan transition (downgrade-guard etc.)
 *   2. Swaps `subscription.plan_id` in the DB
 *   3. Emits SUBSCRIPTION/PLAN_CHANGED audit event
 *   4. Returns the updated row — with `stripe_subscription_id=null`
 *      and `stripe_customer_id=null` because no Stripe call was made
 *
 * This spec asserts that full chain: TA permission → plan transitioned
 * → audit row emitted with correct `old_plan_slug`/`new_plan_slug` →
 * subscription row visible via `verifyViaApi`. A regression in any
 * step fails loud.
 *
 * What this spec does NOT prove (recorded as coverage gap)
 * --------------------------------------------------------
 * The original task line says "against Stripe test-mode". The
 * Stripe-layer assertions — `stripe_subscription_id` populated, Stripe
 * customer created, payment method charged, Invoice row persisted —
 * require:
 *   (a) STRIPE_SECRET_KEY (sk_test_*) in AWS Secrets Manager at
 *       `staging/hub/stripe`
 *   (b) `externalSecrets.stripe.enabled: true` in
 *       helm/values.staging.yaml
 *   (c) A pre-seeded Stripe Test Customer for the tenant with an
 *       attached payment method (pm_card_visa)
 *
 * When any of (a)/(b)/(c) is missing the backend silently skips Stripe
 * — the business-logic assertions still pass, so this spec stays green
 * and honest. When all three land, the conditional Stripe-assertion
 * branch at the end of the test activates automatically. Each side is
 * labelled in test.info().annotations so the skip-counter / flake-
 * annotation reporters surface the gap for Track H.
 *
 * All assertions run against the real backend — no mocks/stubs.
 */

import { expect, test } from '@playwright/test';
import { getTenantAdminUser, loginUser } from '../../fixtures/auth';
import { verifyViaApi } from '../../fixtures/verifyViaApi';
import { verifyAuditEvent } from '../../fixtures/verifyAuditEvent';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

interface Subscription {
  id: string;
  tenant: string;
  plan: string;
  plan_slug: string;
  plan_name: string;
  plan_tier: string;
  status: string;
  stripe_subscription_id: string | null;
  stripe_customer_id: string | null;
  created_at: string;
  updated_at: string;
}

interface Plan {
  id: string;
  slug: string;
  tier: string;
  category: string;
  is_active: boolean;
  price_amount_cents?: number;
}

test.describe('JOURNEY-TA-BILLING-UPGRADE: UC-BILL-002 Billing Upgrade', () => {
  test.setTimeout(180_000);

  test('TA changes plan → subscription reflects new plan → audit row emitted', async ({
    page,
  }) => {
    const taUser = await getTenantAdminUser();
    await loginUser(page, taUser);
    await expect(page.locator('.app-header')).toBeVisible({ timeout: 15_000 });

    const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
    if (!accessToken) {
      throw new Error(
        'JOURNEY-TA-BILLING-UPGRADE: localStorage access_token null after loginUser.',
      );
    }

    // ─────────────────────────────────────────────────────────────────
    // Step 1 — Capture current subscription baseline.
    //
    // Staging seeds the TA tenant with "E2E Unlimited Plan" (tier
    // ENTERPRISE, price 0). We read the current slug so we can (a)
    // pick a DIFFERENT plan for the upgrade and (b) revert at the end
    // so the test is idempotent.
    // ─────────────────────────────────────────────────────────────────
    const subListRes = await page.request.get(`${API_BASE}/billing/subscription/`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(subListRes.status(), 'GET /billing/subscription/ expected 200').toBe(200);
    const subList = (await subListRes.json()) as { results?: Subscription[] } | Subscription[];
    const subs = Array.isArray(subList) ? subList : subList.results ?? [];
    expect(subs.length, 'TA tenant must have at least one subscription').toBeGreaterThan(0);
    const originalSub = subs[0];
    const originalPlanSlug = originalSub.plan_slug;
    const subscriptionId = originalSub.id;

    console.log(
      `[TA-BILLING-UPGRADE] subscription=${subscriptionId.slice(0, 8)} ` +
        `currentPlan=${originalPlanSlug} tier=${originalSub.plan_tier} ` +
        `stripeCustomerId=${originalSub.stripe_customer_id ?? 'null'}`,
    );

    // ─────────────────────────────────────────────────────────────────
    // Step 2 — Pick a target plan that is NOT the current one.
    //
    // Prefer a non-free, non-enterprise BASE plan so the upgrade
    // exercises a real plan-limits change. Fall back to ANY different
    // active BASE plan if no PRO tier is available (a fresh staging
    // instance may only seed the free + enterprise tiers).
    // ─────────────────────────────────────────────────────────────────
    const plansRes = await page.request.get(`${API_BASE}/billing/plans/`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(plansRes.status(), 'GET /billing/plans/ expected 200').toBe(200);
    const plansBody = (await plansRes.json()) as { results?: Plan[] } | Plan[];
    const allPlans = Array.isArray(plansBody) ? plansBody : plansBody.results ?? [];
    const candidates = allPlans.filter(
      (p) => p.slug !== originalPlanSlug && p.is_active !== false && p.category === 'BASE',
    );
    const targetPlan =
      candidates.find((p) => p.tier !== 'FREE' && p.tier !== 'ENTERPRISE') ??
      candidates[0];
    test.skip(
      !targetPlan,
      'No alternative active BASE plan available in this tenant — staging seeding needs >= 2 BASE plans for this test.',
    );
    if (!targetPlan) return;

    console.log(`[TA-BILLING-UPGRADE] upgrading to target=${targetPlan.slug} tier=${targetPlan.tier}`);

    // ─────────────────────────────────────────────────────────────────
    // Step 3 — POST the change-plan request.
    //
    // The endpoint is the canonical entry point for UC-BILL-002.
    // Backend route + action: hub/apps/billing/views.py:197
    // url_path='current/change-plan'.
    // ─────────────────────────────────────────────────────────────────
    const upgradeRes = await page.request.post(
      `${API_BASE}/billing/subscription/current/change-plan/`,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        data: { plan_slug: targetPlan.slug },
      },
    );
    const upgradeBody = await upgradeRes.text();
    expect(
      upgradeRes.status(),
      `change-plan expected 200 when upgrading from ${originalPlanSlug} to ${targetPlan.slug}. ` +
        `Body: ${upgradeBody.slice(0, 400)}`,
    ).toBe(200);
    const upgraded = JSON.parse(upgradeBody) as Subscription;
    expect(upgraded.plan_slug).toBe(targetPlan.slug);
    expect(upgraded.id).toBe(subscriptionId);

    // ─────────────────────────────────────────────────────────────────
    // Step 4 — Dual-channel: fresh GET proves persistence.
    //
    // The POST response is authoritative for the handler's output, but
    // a subsequent GET is authoritative for what OTHER requests will
    // see. Both must agree on the new plan.
    // ─────────────────────────────────────────────────────────────────
    await verifyViaApi(
      page,
      `/api/v1/billing/subscription/${subscriptionId}/`,
      (body: Subscription) => body.plan_slug === targetPlan.slug && body.id === subscriptionId,
    );

    // ─────────────────────────────────────────────────────────────────
    // Step 5 — Audit-trail verification.
    //
    // hub/apps/billing/views.py:273-286 emits:
    //   resource_type="SUBSCRIPTION"
    //   action="PLAN_CHANGED"
    //   resource_id=<subscription.id>
    //   details={ old_plan_slug, new_plan_slug, subscription_id }
    //
    // verifyAuditEvent polls the audit-events endpoint until a matching
    // row appears (up to the default budget) — handles sync/async
    // emission transparently.
    // ─────────────────────────────────────────────────────────────────
    await verifyAuditEvent(page, {
      action: 'PLAN_CHANGED',
      resourceType: 'SUBSCRIPTION',
      resourceId: subscriptionId,
    });

    // ─────────────────────────────────────────────────────────────────
    // Step 6 — Stripe-layer assertion (conditional on Stripe being
    // wired).
    //
    // Rationale: the POST /change-plan/ response's serializer omits
    // null stripe_* fields (see SubscriptionSerializer — nullable
    // fields drop from the JSON when null), so reading them from the
    // POST body can't distinguish "null" from "absent". Fetch a fresh
    // GET of the subscription — its serializer emits explicit nulls,
    // which is the shape this branching expects.
    //
    // If the fresh-GET shows a populated `stripe_customer_id`, the
    // backend has an active Stripe customer and the upgrade went
    // through Stripe — so `stripe_subscription_id` MUST also be
    // populated (the subscription gets a new si_* item ID when
    // Stripe is in play).
    //
    // If `stripe_customer_id` is null/undefined, Stripe isn't
    // configured on this environment; record the gap as an
    // annotation so the flake-annotation reporter / skip-counter
    // gate surfaces it for Track H, and the test stays honest
    // about what it didn't verify.
    // ─────────────────────────────────────────────────────────────────
    const freshRes = await page.request.get(
      `${API_BASE}/billing/subscription/${subscriptionId}/`,
      { headers: { Authorization: `Bearer ${accessToken}` } },
    );
    expect(freshRes.status(), 'fresh GET for Stripe-branch decision expected 200').toBe(200);
    const fresh = (await freshRes.json()) as Subscription;
    const stripeWired = fresh.stripe_customer_id != null;

    if (stripeWired) {
      expect(
        fresh.stripe_subscription_id,
        'Stripe-wired tenant: stripe_subscription_id must be populated after plan change.',
      ).not.toBeNull();
      console.log(
        `[TA-BILLING-UPGRADE] Stripe-wired: customer=${fresh.stripe_customer_id} ` +
          `subscription=${fresh.stripe_subscription_id}`,
      );
    } else {
      test.info().annotations.push({
        type: 'phase226-stripe-not-wired',
        description:
          'stripe_customer_id is null on the post-upgrade subscription. ' +
          'Backend is taking the non-Stripe path — STRIPE_SECRET_KEY not set ' +
          'and/or externalSecrets.stripe.enabled is false in helm/values.staging.yaml. ' +
          'Stripe-layer assertions skipped. Unblock: wire STRIPE_SECRET_KEY via ' +
          'AWS Secrets Manager at staging/hub/stripe + flip externalSecrets.stripe.enabled.',
      });
      console.log(
        '[TA-BILLING-UPGRADE] Stripe not wired — business-logic upgrade ran, ' +
          'Stripe-layer assertions skipped with annotation.',
      );
    }

    // ─────────────────────────────────────────────────────────────────
    // Step 7 — Revert to original plan (idempotence / cleanup).
    //
    // Leaving the TA tenant on a non-original plan would interfere
    // with subsequent runs (the upgrade would be to "already on this
    // plan" and 400 at step 3). Revert best-effort; if it fails the
    // unique per-test plan selection above still keeps individual
    // test runs green, but cross-spec drift could accumulate.
    // ─────────────────────────────────────────────────────────────────
    const revertRes = await page.request.post(
      `${API_BASE}/billing/subscription/current/change-plan/`,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        data: { plan_slug: originalPlanSlug },
      },
    );
    // Don't fail the test on revert failure — the primary assertions
    // above have already passed. Record a diagnostic for the nightly
    // cleanup job to sweep if this recurs.
    if (!revertRes.ok()) {
      // intentional: tolerates non-text / streaming response body when
      // building a diagnostic message; the console.warn below this
      // catch is diagnostic output only — the test's verdict is
      // already steps 1-6.
      const body = await revertRes.text().catch(() => '');
      console.warn(
        `[TA-BILLING-UPGRADE] revert to ${originalPlanSlug} failed: ${revertRes.status()} ` +
          `${body.slice(0, 300)}`,
      );
    }
  });
});
