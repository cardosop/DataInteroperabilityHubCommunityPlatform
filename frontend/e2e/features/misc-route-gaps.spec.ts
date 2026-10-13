/**
 * E2E Feature: Miscellaneous route gaps (close-test-coverage-gaps task 4.6).
 *
 * Surfaces under test:
 *   /marketplace/orders/:id              (OrderDetailPage)
 *   /dq/runs/:id/rca                     (RootCauseAnalysisPage)
 *   /ml/inference/:id                    (InferenceMetricsPage)
 *   /baas/customers/:customerId          (CustomerDetailPage)
 *   /baas/billing-reports/:reportId      (BillingReportDetailPage)
 *
 * Seeding:
 *   - The marketplace order is placed through the REAL API chain the
 *     product uses (createListingViaApi → publishListingViaApi →
 *     placeOrderViaApi as a CONSUMER user) in the DEFAULT test tenant —
 *     no ORM writes.
 *   - The DQ run, BAAS customer (API key + billing report) are seeded
 *     via docker-exec manage.py shell into a scratch tenant (the
 *     4.2/4.3 canonical pattern — the disposable-tenant fixture's
 *     ephemeral endpoint is disabled on this stack). The billing-reports
 *     ViewSet is read-only, so ORM seeding is the only path for a
 *     report row.
 *   - The ML inference surface asserts the REAL error contract for a
 *     missing deployment id on an ml-enabled tenant: the route is wired
 *     (the SPA reaches the API, NOT /unavailable) and the page surfaces
 *     the real error display. (The deployments endpoint probes ODH,
 *     which is down on this stack — 503 — so a live deployment row
 *     cannot render here; the missing-id error pin is deterministic.)
 *
 * Assertions target FETCHED DOM (rendered rows, names, statuses) —
 * never a bare shell. Real backend only — no mocks, no stubs.
 */
import { execSync } from 'node:child_process';
import { expect, test } from '@playwright/test';
import { createAssetViaApi } from '../fixtures/api-assets';
import {
  createListingViaApi,
  placeOrderViaApi,
  publishListingViaApi,
} from '../fixtures/api-marketplace';
import {
  getConsumerTestUser,
  getTestUser,
  gotoWithRetry,
  loginUser,
  type TestUser,
} from '../fixtures/auth';
import { skipIfRemoteApi } from '../fixtures/helpers';

const NIL_UUID = '00000000-0000-0000-0000-000000000000';
const PASSWORD = 'testpass123';

interface Provisioned {
  email: string;
  dqRunId: string;
  customerId: string;
  reportId: string;
}

function toTestUser(email: string): TestUser {
  return { email, password: PASSWORD, name: email.split('@')[0] };
}

/** Memoized per-worker: one docker-exec provisions the scratch tenant. */
let cached: Provisioned | null = null;

function provision(): Provisioned {
  if (cached) return cached;
  skipIfRemoteApi(
    test,
    'misc-route-gaps scratch-tenant provisioning requires docker exec on the test API container',
  );
  const suffix = Math.random().toString(16).slice(2, 10);
  const script = `
import json
from datetime import timedelta

from django.utils import timezone
from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan
from hub.apps.users.models import Role, User, UserRole, UserStatus

suffix = "${suffix}"
tenant = Tenant.objects.create(
    name=f"e2e-miscr-{suffix}", slug=f"e2e-miscr-{suffix}",
    status="ACTIVE", kyc_status=KYCStatus.VERIFIED,
)
tenant.data_quality_enabled = True
tenant.data_quality_advanced_enabled = True
tenant.baas_enabled = True
tenant.ml_enabled = True
tenant.save(update_fields=[
    "data_quality_enabled", "data_quality_advanced_enabled",
    "baas_enabled", "ml_enabled",
])
from hub.apps.billing.models import Subscription, SubscriptionStatus
plan, _ = TenantPlan.objects.get_or_create(
    slug=f"miscr-plan-{suffix}",
    defaults={
        "name": f"MiscRoutes Plan {suffix}", "tier": PlanTier.FREE,
        "is_active": True, "limits_json": {"max_assets": 100},
    },
)
Subscription.objects.create(
    tenant=tenant, plan=plan, status=SubscriptionStatus.ACTIVE,
    current_period_start=timezone.now(),
    current_period_end=timezone.now() + timedelta(days=365),
)
user = User.objects.create_user(
    email=f"miscr-{suffix}@test.com", password="${PASSWORD}",
    tenant=tenant, status=UserStatus.ACTIVE,
)
role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
UserRole.objects.get_or_create(user=user, role=role)

# DQ run + asset (the /dq/runs/:id/rca page reads the run's asset).
# DQRun.job is a REQUIRED FK — a real Job row must exist.
import uuid as _uuid
from hub.apps.assets.models import Asset
from hub.apps.dq.models import DQRun
from hub.apps.jobs.models import Job
asset = Asset.objects.create(
    tenant=tenant, name=f"e2e-miscr-asset-{suffix}", status="ACTIVE",
)
job = Job.objects.create(
    tenant=tenant, type="DQ_RUN", status="COMPLETED", priority="NORMAL",
    resource_type="ASSET", resource_id=_uuid.uuid4(), created_by=user,
)
dq_run = DQRun.objects.create(
    tenant=tenant, asset=asset, job=job, profile_key="intake_basic",
    engine="SODA", status="SUCCEEDED", overall_status="PASSED",
    checks_json={"checks": []}, details_json={"detail": "e2e-seeded"},
    sampled=False, quality_score=98.0,
)

# BAAS customer (API key carries the customer identity) + billing report.
from hub.apps.baas.models import (
    APIKey, APITierModel, CustomerBillingReport,
)
tier, _ = APITierModel.objects.get_or_create(
    name=f"E2E-Tier-{suffix}",
    defaults={
        "rate_limit_per_hour": 1000, "rate_limit_per_day": 10000,
        "max_requests_per_month": 100000, "price_per_month": "0.00",
        "features": {}, "scopes": "api:read api:write",
    },
)
api_key = APIKey.objects.create(
    tenant=tenant, user=user, tier=tier, name=f"e2e-cust-{suffix}",
    key_hash=f"miscr-{suffix}",
    scopes="api:read",
)
report = CustomerBillingReport.objects.create(
    # api_key is NULLABLE and points at the AUTH app's key model
    # (hub_auth.APIKey) — the BAAS developer-portal key is a different
    # model, so the report is seeded key-less; the detail page resolves
    # it by customer_id.
    tenant=tenant,
    customer_id=f"cust-{suffix}",
    customer_name=f"Acme E2E {suffix}",
    customer_email=f"cust-{suffix}@test.com",
    period_start=timezone.now() - timedelta(days=30),
    period_end=timezone.now(),
    total_requests=1200, billable_requests=1150,
    status="DRAFT",
)
print(json.dumps({
    "email": user.email,
    "dqRunId": str(dq_run.id),
    "customerId": f"cust-{suffix}",
    "reportId": str(report.id),
}))
`;
  const out = execSync('docker exec -i hub-test-api python hub/manage.py shell', {
    encoding: 'utf-8',
    timeout: 120000,
    input: script,
  });
  const lines = out.split('\n').filter((line) => line.trim().startsWith('{"email"'));
  expect(lines.length, `provisioning failed: ${out.slice(0, 400)}`).toBeGreaterThan(0);
  cached = JSON.parse(lines[0].trim()) as Provisioned;
  return cached;
}

test.describe('Feature: Miscellaneous route gaps (task 4.6)', () => {
  test.setTimeout(240000);

  test('marketplace order detail renders the real order (API-placed)', async ({ page }) => {
    // Full real API chain in the default tenant: provider creates +
    // publishes a listing, the CONSUMER tenant places the order.
    // Conditional skips (the repo's guarded pattern) — the marketplace
    // capability is environment-dependent; never a bare test.skip(true).
    const provider = await getTestUser();
    let listingId: string | null = null;
    let listingGatedReason: string | null = null;
    try {
      // createListingViaApi requires the provider's asset id (the
      // listing wraps a real asset) — seed the asset via the REAL
      // asset-create API first. The asset MUST be ACTIVATED: the listing
      // business rule refuses DRAFT assets (400 BUSINESS_RULES_VALIDATION
      // "Asset must be ACTIVE to be listed") — without activation the
      // chain is gated and the journey silently skipped (f7 batch,
      // 2026-10-03). ensureActivated provisions the E2E prerequisites
      // (ODCS contract) + activation; forceNew avoids reusing a DRAFT
      // asset left behind by an earlier partial run.
      const assetId = await createAssetViaApi(provider, { ensureActivated: true, forceNew: true });
      listingId = await createListingViaApi(provider, assetId);
      await publishListingViaApi(provider, listingId);
    } catch (err) {
      listingGatedReason =
        `listing create/publish gated: ${(err as Error).message.slice(0, 120)} — environment-dependent marketplace capability`;
    }
    test.skip(listingGatedReason !== null, listingGatedReason ?? '');
    if (listingGatedReason) return;

    const consumer = await getConsumerTestUser();
    let orderId: string | null = null;
    let orderGatedReason: string | null = null;
    try {
      orderId = await placeOrderViaApi(consumer, listingId as string);
    } catch (err) {
      orderGatedReason =
        `order placement gated: ${(err as Error).message.slice(0, 120)} — environment-dependent`;
    }
    test.skip(orderGatedReason !== null, orderGatedReason ?? '');
    if (orderGatedReason) return;

    await loginUser(page, consumer);
    await gotoWithRetry(page, `/marketplace/orders/${orderId}`);
    // The real order detail: the order heading, the id label, and the
    // FREE_AUTO_APPROVE flow's success state (the API chain placed +
    // fulfilled the order — real fetched DOM).
    await expect(
      page.getByRole('heading', { name: `Order ${orderId?.slice(0, 8)}` }),
      'order heading renders the seeded order id',
    ).toBeVisible({ timeout: 30000 });
    await expect(page.getByText('Order ID')).toBeVisible();
    await expect(page.getByText(/Order fulfilled/)).toBeVisible();
  });

  test('dq root-cause-analysis route renders the real RCA page for a seeded run', async ({
    page,
  }) => {
    const env = provision();
    await loginUser(page, toTestUser(env.email));
    await gotoWithRetry(page, `/dq/runs/${env.dqRunId}/rca`);
    await expect(page.getByTestId('rca-page')).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole('heading', { name: 'Root Cause Analysis' })).toBeVisible();
    // The seeded run's context drives the real filters/summary surface.
    await expect(page.locator('.dq-results-subtitle')).toBeVisible();
  });

  test('ml inference detail route is wired on an ml-enabled tenant (real error contract)', async ({
    page,
  }) => {
    const env = provision();
    await loginUser(page, toTestUser(env.email));
    await gotoWithRetry(page, `/ml/inference/${NIL_UUID}`);
    // Route-wiring pin: the capability gate is OPEN for the ml_enabled
    // tenant (never /unavailable) and the page surfaces the REAL API
    // error for the missing deployment id (the deployments endpoint
    // probes ODH, which is down on this stack, so a live row cannot
    // render — the error display is the deterministic fetched-DOM pin).
    await expect(page.locator('[data-testid="disabled-capability-page"]')).toHaveCount(0, {
      timeout: 30000,
    });
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).toBeVisible({
      timeout: 30000,
    });
  });

  test('baas customer detail renders the seeded customer identity + reports', async ({
    page,
  }) => {
    const env = provision();
    await loginUser(page, toTestUser(env.email));
    await gotoWithRetry(page, `/baas/customers/${env.customerId}`);
    await expect(page.locator('.customer-detail-page')).toBeVisible({ timeout: 30000 });
    // The customer identity lives on the BillingReport model — the page
    // heading falls back to the raw customer_id (the list serializer
    // never carries customer_name), while the Billing History rows
    // render the report's stored identity.
    await expect(
      page.getByRole('heading', { name: env.customerId }),
      'customer heading renders (raw customer_id fallback)',
    ).toBeVisible({ timeout: 30000 });
    // The Billing History table renders the seeded report row (the
    // customer view does NOT render customer_name — that lives on the
    // report detail page).
    const historyRow = page.getByRole('row').filter({ hasText: 'DRAFT' });
    await expect(historyRow).toBeVisible({ timeout: 30000 });
    await expect(historyRow).toContainText('1,200');
  });

  test('baas billing-report detail renders the seeded report', async ({ page }) => {
    const env = provision();
    await loginUser(page, toTestUser(env.email));
    await gotoWithRetry(page, `/baas/billing-reports/${env.reportId}`);
    // The report detail surfaces the customer identity + the seeded
    // request totals (real fetched DOM). The name renders twice (label
    // + summary block) — pin the heading + one instance + the status
    // badge + the totals.
    await expect(page.getByRole('heading', { name: 'Billing Report' })).toBeVisible({
      timeout: 30000,
    });
    await expect(
      page.getByText(`Acme E2E ${env.customerId.replace('cust-', '')}`).first(),
    ).toBeVisible({ timeout: 30000 });
    await expect(page.getByText('DRAFT')).toBeVisible();
    await expect(page.getByText('1,200')).toBeVisible();
  });
});
