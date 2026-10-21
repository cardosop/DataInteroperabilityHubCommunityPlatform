/**
 * E2E Feature: Edit screens (close-test-coverage-gaps task 4.3).
 *
 * Surfaces under test:
 *   /scheduled-ingestions/:id/edit   (ScheduledIngestionEditPage)
 *   /scheduled-exports/:id/edit      (ScheduledExportEditPage)
 *   /webhooks/:id/edit               (WebhookEditPage)
 *   /integrations/connections/:id/edit (MarketplaceConnectionEditPage)
 *   /contracts/:id/lineage/edit      (LineageEditPage)
 *
 * Seeding strategy (the task's "seed parents via API first"):
 *   - the scratch TENANT shell (tenant + TENANT_ADMIN user) is
 *     provisioned via docker-exec manage.py shell — the canonical
 *     pattern of axe-databricks-ml-assets.spec.ts and
 *     databricks-deep-routes.spec.ts. NOTE: the disposable-tenant
 *     fixture (POST /api/v1/tenants/ephemeral/) is DISABLED on this
 *     stack ("ephemeral tenant endpoint is not enabled in this
 *     environment" — 404), so docker-exec is the working equivalent.
 *   - the PARENT ROWS (scheduled ingestion, scheduled export, webhook,
 *     contract) are seeded through the REAL HTTP create endpoints with
 *     the scratch admin's bearer token — real serializers, real
 *     validation, no ORM writes.
 *
 * Assertions target FETCHED DOM — prefilled form values, rendered
 * panes — never a bare shell. The connections surface needs the
 * marketplace capability (tenant flag + KYC), so that one test runs
 * against the DEFAULT test tenant and conditionally skips when the
 * create API is gated (the documented environment-dependent pattern).
 *
 * Real backend only — no mocks, no stubs.
 */
import { execSync } from 'node:child_process';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { createAssetViaApi, createODCSContractViaApi } from '../fixtures/api-assets';
import { getTestUser, gotoWithRetry, loginUser, type TestUser } from '../fixtures/auth';
import { skipIfRemoteApi } from '../fixtures/helpers';

const API_BASE = '/api/v1';
const NIL_UUID = '00000000-0000-0000-0000-000000000000';
const PASSWORD = 'testpass123';

interface Provisioned {
  email: string;
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
    'edit-screens scratch-tenant provisioning requires docker exec on the test API container',
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
    name=f"e2e-editscr-{suffix}", slug=f"e2e-editscr-{suffix}",
    status="ACTIVE", kyc_status=KYCStatus.VERIFIED,
)
# Active subscription: the /scheduled-* subtrees are subscription-gated.
from hub.apps.billing.models import Subscription, SubscriptionStatus
plan, _ = TenantPlan.objects.get_or_create(
    slug=f"editscr-plan-{suffix}",
    defaults={
        "name": f"EditScreens Plan {suffix}", "tier": PlanTier.FREE,
        "is_active": True, "limits_json": {"max_assets": 100},
    },
)
Subscription.objects.create(
    tenant=tenant, plan=plan, status=SubscriptionStatus.ACTIVE,
    current_period_start=timezone.now(),
    current_period_end=timezone.now() + timedelta(days=365),
)
user = User.objects.create_user(
    email=f"editscr-{suffix}@test.com", password="${PASSWORD}",
    tenant=tenant, status=UserStatus.ACTIVE,
)
role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
UserRole.objects.get_or_create(user=user, role=role)
print(json.dumps({"email": user.email}))
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

/** Login via the REAL login endpoint; returns the bearer access token. */
async function apiLogin(page: Page, user: TestUser): Promise<string> {
  const res = await page.request.post(`${API_BASE}/auth/login/`, {
    data: { email: user.email, password: user.password },
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok()) {
    throw new Error(
      `apiLogin for ${user.email} returned ${res.status()}: ${(await res.text()).slice(0, 200)}`,
    );
  }
  const body = (await res.json()) as { access_token?: string };
  if (!body.access_token) {
    throw new Error(`apiLogin for ${user.email} returned no access_token`);
  }
  return body.access_token;
}

/** Seed a parent row through the REAL create endpoint. */
async function seedViaApi(
  page: Page,
  token: string,
  path: string,
  payload: Record<string, unknown>,
): Promise<string> {
  const res = await page.request.post(`${API_BASE}${path}`, {
    data: payload,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  });
  if (!res.ok()) {
    throw new Error(
      `seed POST ${path} returned ${res.status()}: ${(await res.text()).slice(0, 300)}`,
    );
  }
  const body = (await res.json()) as { id?: string };
  if (!body.id) {
    throw new Error(`seed POST ${path} returned no id: ${JSON.stringify(body).slice(0, 200)}`);
  }
  return body.id;
}

test.describe('Feature: Edit screens (task 4.3)', () => {
  test.setTimeout(240000);

  test('scheduled-ingestion edit screen prefills the seeded row and saves a rename', async ({
    page,
  }) => {
    const user = toTestUser(provision().email);
    const token = await apiLogin(page, user);
    const id = await seedViaApi(page, token, '/scheduled-ingestions/', {
      name: 'e2e-edit-ingestion',
      description: 'Seeded for the edit-screen spec',
      source_type: 'S3',
      source_config: { bucket: 'e2e-seeds', prefix: 'edit-screens/', region: 'us-east-1' },
      schedule_type: 'DAILY',
      schedule_config: { time: '02:00' },
      file_pattern: '.*',
      test_connection: false,
    });

    await loginUser(page, user);
    await gotoWithRetry(page, `/scheduled-ingestions/${id}/edit`);
    await expect(
      page.getByTestId('scheduled-ingestion-edit-page'),
      'edit page shell renders',
    ).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole('heading', { name: 'Edit Scheduled Ingestion' })).toBeVisible();

    // Fetched-DOM prefill: the real row drives the form values.
    await expect(page.locator('#name')).toHaveValue('e2e-edit-ingestion');
    await expect(page.locator('#description')).toHaveValue('Seeded for the edit-screen spec');
    await expect(page.locator('#source_type')).toHaveValue('S3');
    await expect(page.locator('#schedule_type')).toHaveValue('DAILY');

    // Real save flow: rename + submit → lands on the detail screen.
    await page.locator('#name').fill('e2e-edit-ingestion-renamed');
    await page.locator('#description').fill('');
    await page.getByRole('button', { name: 'Update' }).click();
    await expect(page).toHaveURL(new RegExp(`/scheduled-ingestions/${id}$`));
  });

  test('scheduled-export edit screen prefills the seeded row', async ({ page }) => {
    const user = toTestUser(provision().email);
    const token = await apiLogin(page, user);
    // source_scope must reference a real row (the serializer rejects an
    // empty scope with "at least one of: asset_ids, ...") — seed the
    // asset through the REAL asset-create API first.
    const assetId = await createAssetViaApi(user, { forceNew: true });
    const id = await seedViaApi(page, token, '/scheduled-exports/', {
      name: 'e2e-edit-export',
      schedule_config: { cron: '0 3 * * *', timezone: 'UTC' },
      destination_type: 'S3',
      destination_config: { bucket: 'e2e-seeds', prefix: 'exports/' },
      source_scope: { asset_ids: [assetId] },
    });

    await loginUser(page, user);
    await gotoWithRetry(page, `/scheduled-exports/${id}/edit`);
    await expect(
      page.getByTestId('scheduled-export-edit-page'),
      'edit page shell renders',
    ).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole('heading', { name: 'Edit Scheduled Export' })).toBeVisible();
    await expect(page.locator('#name')).toHaveValue('e2e-edit-export');
    await expect(page.locator('#cron')).toHaveValue('0 3 * * *');
    await expect(page.locator('#destination_type')).toHaveValue('S3');
  });

  test('webhook edit screen prefills the seeded webhook', async ({ page }) => {
    const user = toTestUser(provision().email);
    const token = await apiLogin(page, user);
    const id = await seedViaApi(page, token, '/webhooks/webhooks/', {
      name: 'e2e-edit-webhook',
      url: 'https://example.com/hooks/e2e-edit',
      secret: 'e2e-secret-edit',
      event_types: ['asset.updated'],
    });

    await loginUser(page, user);
    await gotoWithRetry(page, `/webhooks/${id}/edit`);
    await expect(page.getByRole('heading', { name: 'Edit webhook' })).toBeVisible({
      timeout: 30000,
    });
    await expect(page.locator('#webhook-edit-name')).toHaveValue('e2e-edit-webhook');
    await expect(page.locator('#webhook-edit-url')).toHaveValue(
      'https://example.com/hooks/e2e-edit',
    );
    // The seeded event type is checked in the real checkbox list (the
    // labels render the human-readable choice — "Asset Updated").
    const checked = page.locator('input[type="checkbox"]:checked');
    await expect(checked).toHaveCount(1);
    await expect(checked.first().locator('..')).toContainText('Asset Updated');
  });

  test('contract lineage edit screen renders the real editor with schema fields', async ({
    page,
  }) => {
    // Parent contract: seeded through the REAL contract-create API with
    // the repo's canonical ODCS payload (createODCSContractViaApi — the
    // same helper the ODPS-Link E2E uses). A bare ODPS-shaped document
    // fails the structural-floor chain (STRUCTURELESS_ODCS_NO_SCHEMA),
    // so the ODCS spec shape is the contract.
    const user = toTestUser(provision().email);
    const contractId = await createODCSContractViaApi(user, { forceNew: true });

    await loginUser(page, user);
    await gotoWithRetry(page, `/contracts/${contractId}/lineage/edit`);
    await expect(page.getByTestId('lineage-edit-page')).toBeVisible({ timeout: 30000 });
    // Real copy from the editor's namespaced strings module
    // (lineageEditorStrings.ts).
    await expect(page.getByRole('heading', { name: 'Edit lineage' })).toBeVisible();
    // The seeded schema drives the source/target field panes (heading
    // role — the subtitle paragraph also contains "source fields").
    await expect(page.getByRole('heading', { name: 'Source fields' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Target fields' })).toBeVisible();
    // Honest empty edge state — a fresh contract has no lineage edges,
    // so the empty copy renders (the "Mapping" heading + table only
    // render once an edge exists).
    await expect(page.getByText(/No edges yet/)).toBeVisible();
    // The editor toolbar is the real action surface.
    await expect(page.getByRole('button', { name: 'Add edge' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save changes' })).toBeVisible();
  });

  test('nonexistent scheduled-ingestion edit shows the real error display', async ({
    page,
  }) => {
    const user = toTestUser(provision().email);
    await loginUser(page, user);
    await gotoWithRetry(page, `/scheduled-ingestions/${NIL_UUID}/edit`);
    await expect(
      page.getByRole('heading', { name: 'Failed to load scheduled ingestion' }),
    ).toBeVisible({
      timeout: 30000,
    });
  });

  test.describe('connections edit (default tenant — marketplace capability required)', () => {
    test('marketplace connection edit screen prefills the seeded connection', async ({
      page,
    }) => {
      const user = await getTestUser();
      const token = await apiLogin(page, user);

      // The create endpoint is gated by the marketplace-integrations
      // tenant flag + integrations:write scope — environment-dependent.
      // Conditional skip (the repo's guarded pattern), never a bare
      // test.skip(true, ...). One retry: batch-run load can 429 the
      // create (the transient-flake class this spec hit in its first
      // full pass). The name is UNIQUE per run — connection names are
      // unique-within-tenant and a leftover row from a prior run 409s
      // a fixed name.
      const connectionName = `e2e-edit-connection-${Date.now()}`;
      const payload = {
        marketplace_type: 'SNOWFLAKE_DATA_MARKETPLACE',
        name: connectionName,
        config: { account: 'e2e', role: 'SEED' },
        is_active: true,
      };
      let res = await page.request.post(`${API_BASE}/integrations/marketplace/connections/`, {
        data: payload,
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
      if (!res.ok()) {
        await page.waitForTimeout(1500);
        res = await page.request.post(`${API_BASE}/integrations/marketplace/connections/`, {
          data: payload,
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        });
      }
      const createGated = !res.ok();
      test.skip(
        createGated,
        `marketplace connection create gated (${res.status()} ${(await res.text()).slice(0, 120)}) — environment-dependent capability`,
      );
      if (createGated) return;

      const body = (await res.json()) as { id?: string };
      const missingId = !body.id;
      test.skip(missingId, 'marketplace connection create returned no id');
      if (missingId) return;
      const id: string = body.id;

      await loginUser(page, user);
      await gotoWithRetry(page, `/integrations/connections/${id}/edit`);
      await expect(
        page.getByRole('heading', { name: 'Edit Marketplace Connection' }),
        'edit page shell renders',
      ).toBeVisible({ timeout: 30000 });
      await expect(page.locator('#name')).toHaveValue(connectionName);
      await expect(page.locator('#marketplace_type')).toHaveValue('SNOWFLAKE_DATA_MARKETPLACE');
    });
  });
});
