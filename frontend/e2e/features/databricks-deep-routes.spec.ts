/**
 * E2E Feature: Databricks deep routes (close-test-coverage-gaps task 4.2).
 *
 * Routes under test (routes.tsx, all sharing the SAME gate chain —
 * MvpGatedRoute > CapabilityRoute capability="databricks" >
 * ProtectedRoute TENANT_ADMIN|PLATFORM_ADMIN):
 *
 *   /databricks/workspaces/:workspaceId/jobs          (DatabricksJobsPage)
 *   /databricks/workspaces/:workspaceId/dlt-pipelines (DatabricksDltPipelinesPage)
 *   /databricks/budgets                               (DatabricksBudgetPage)
 *
 * Real backend only — no mocks, no stubs. The provisioning helper seeds REAL
 * rows through the REAL service layer (docker-exec manage.py shell — the
 * canonical pattern of axe-databricks-ml-assets.spec.ts and JOURNEY-DB-011):
 * two scratch tenants (capability ON + OFF), a TENANT_ADMIN user on each, an
 * ACTIVE workspace, and mirror rows for one job + one run. The pages read
 * mirror-first (ZERO live Databricks calls), so the seeded rows drive the
 * real list/expansion endpoints deterministically.
 *
 * Contracts pinned:
 *   - ON tenant: the three deep routes render their real loaded state
 *     (fleet table + run expansion / honest mirror-empty / honest budget-empty)
 *     — no 404 fall-through, no gate bounce.
 *   - OFF tenant: all three routes bounce to /unavailable with
 *     capability-key "databricks" (the CapabilityRoute contract).
 *   - Failure: a nonexistent workspace id surfaces the real 404 error display.
 *   - Anonymous: the RootRoute auth guard (useAuthStore, RootRoute.tsx:31-37)
 *     is OUTERMOST — it redirects to /login before any capability or role
 *     gate resolves. Pinned live: anon → /login, never a 404 fall-through.
 *     (The capability-first ordering applies to AUTHENTICATED visitors.)
 *
 * W16 environment policy governs the only guard: skipIfRemoteApi (local
 * skip, CI raise) around the docker-exec provisioning — never a bare skip.
 */
import { execSync } from 'node:child_process';
import { expect, test } from '@playwright/test';

import { gotoWithRetry, loginUser, type TestUser } from '../fixtures/auth';
import { skipIfRemoteApi } from '../fixtures/helpers';

const NIL_UUID = '00000000-0000-0000-0000-000000000000';
const PASSWORD = 'testpass123';
const JOBS_ROUTE = (workspace: string) => `/databricks/workspaces/${workspace}/jobs`;
const DLT_ROUTE = (workspace: string) => `/databricks/workspaces/${workspace}/dlt-pipelines`;

interface Provisioned {
  on: { email: string; workspace: string };
  off: { email: string };
}

function toTestUser(email: string): TestUser {
  return { email, password: PASSWORD, name: email.split('@')[0] };
}

/** Memoized per-worker: one docker-exec provisions both scratch tenants. */
let cached: Provisioned | null = null;

function provision(): Provisioned {
  if (cached) return cached;
  skipIfRemoteApi(test, 'databricks deep-route provisioning requires docker exec on the test API container');
  const suffix = Math.random().toString(16).slice(2, 10);
  const script = `
import json
from hub.apps.tenants.models import Tenant
from hub.apps.databricks_admin.models import (
    DatabricksCloud, DatabricksJob, DatabricksJobRun, DatabricksWorkspace,
)
from hub.apps.users.models import Role, User, UserRole, UserStatus

suffix = "${suffix}"

def make_tenant(kind, control_plane, dlt):
    tenant = Tenant.objects.create(
        name=f"e2e-dbr-{kind}-{suffix}", slug=f"e2e-dbr-{kind}-{suffix}"
    )
    tenant.databricks_control_plane_enabled = control_plane
    tenant.databricks_dlt_pipelines_enabled = dlt
    tenant.save(update_fields=["databricks_control_plane_enabled", "databricks_dlt_pipelines_enabled"])
    user = User.objects.create_user(
        email=f"dbr-{kind}-{suffix}@test.com", password="${PASSWORD}",
        tenant=tenant, status=UserStatus.ACTIVE,
    )
    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=user, role=role)
    return tenant, user

on_tenant, on_user = make_tenant("on", True, True)
off_tenant, off_user = make_tenant("off", False, False)
workspace = DatabricksWorkspace.objects.create(
    tenant=on_tenant, name=f"ws-deep-{suffix}",
    host="dbc-6710eb95-8fe1.cloud.databricks.com",
    cloud=DatabricksCloud.AWS, region="us-east-1", status="ACTIVE",
)
job = DatabricksJob.objects.create(
    workspace=workspace, job_id="mirror-job-1", name="e2e mirror job",
    task_config=[{"task_key": "ingest"}],
    schedule={"quartz_cron_expression": "0 0 5 * * ?"},
)
DatabricksJobRun.objects.create(
    job=job, run_id="mirror-run-1",
    lifecycle_state="TERMINATED", result_state="SUCCESS", duration_ms=1200,
)
print(json.dumps({
    "on": {"email": on_user.email, "workspace": str(workspace.id)},
    "off": {"email": off_user.email},
}))
`;
  const out = execSync('docker exec -i hub-test-api python hub/manage.py shell', {
    encoding: 'utf-8',
    timeout: 120000,
    input: script,
  });
  const lines = out.split('\n').filter((line) => line.trim().startsWith('{"on"'));
  expect(lines.length, `provisioning failed: ${out.slice(0, 400)}`).toBeGreaterThan(0);
  cached = JSON.parse(lines[0].trim()) as Provisioned;
  return cached;
}

test.describe('Feature: Databricks deep routes', () => {
  test.setTimeout(240000);

  test('jobs deep route renders the real fleet with the seeded mirror row + run expansion', async ({ page }) => {
    const env = provision();
    await loginUser(page, toTestUser(env.on.email));
    await page.goto(JOBS_ROUTE(env.on.workspace));
    await expect(page.getByRole('heading', { name: 'Databricks jobs' })).toBeVisible({ timeout: 30000 });
    const row = page.locator('tr[data-job="mirror-job-1"]');
    await expect(row).toBeVisible({ timeout: 30000 });
    await expect(row).toContainText('e2e mirror job');
    await expect(row).toContainText('scheduled');
    await row.getByRole('button', { name: 'View runs' }).click();
    const run = page.locator('tr[data-run="mirror-run-1"]');
    await expect(run).toBeVisible();
    await expect(run).toContainText('TERMINATED');
    await expect(run).toContainText('SUCCESS');
  });

  test('dlt deep route renders the real mirrored-pipeline state (honest empty)', async ({ page }) => {
    const env = provision();
    await loginUser(page, toTestUser(env.on.email));
    await page.goto(DLT_ROUTE(env.on.workspace));
    await expect(page.getByRole('heading', { name: 'DLT Pipelines' })).toBeVisible({ timeout: 30000 });
    await expect(page.getByTestId('dlt-empty')).toHaveText('No DLT pipelines mirrored yet.');
  });

  test('budgets route renders the real budget list (honest empty)', async ({ page }) => {
    const env = provision();
    await loginUser(page, toTestUser(env.on.email));
    await page.goto('/databricks/budgets');
    await expect(page.getByRole('heading', { name: 'Databricks cost budgets' })).toBeVisible({ timeout: 30000 });
    await expect(page.locator('.budget-list')).toContainText('No cost budgets configured yet.');
  });

  test('capability-off tenant is gated to /unavailable with capability-key databricks on all three routes', async ({ page }) => {
    const env = provision();
    await loginUser(page, toTestUser(env.off.email));
    const routes = [JOBS_ROUTE(NIL_UUID), DLT_ROUTE(NIL_UUID), '/databricks/budgets'];
    for (const route of routes) {
      await gotoWithRetry(page, route);
      await expect(page.locator('[data-testid="disabled-capability-page"]')).toBeVisible({
        timeout: 30000,
      });
      await expect(page.getByTestId('capability-key')).toHaveText('databricks');
    }
  });

  test('nonexistent workspace surfaces the real 404 error display on the jobs route', async ({ page }) => {
    const env = provision();
    await loginUser(page, toTestUser(env.on.email));
    await gotoWithRetry(page, JOBS_ROUTE(NIL_UUID));
    await expect(page.locator('[data-testid="action-error"]')).toBeVisible({ timeout: 30000 });
  });

  test.describe('anonymous visitors', () => {
    // Clean context — the chromium project's shared storageState logs every
    // test in as the default persona user, which would defeat an anon pin.
    test.use({ storageState: { cookies: [], origins: [] } });

    test('are redirected to /login by the outer auth guard, never a 404 fall-through', async ({ page }) => {
      const routes = [JOBS_ROUTE(NIL_UUID), DLT_ROUTE(NIL_UUID), '/databricks/budgets'];
      for (const route of routes) {
        await gotoWithRetry(page, route);
        // The redirect is CLIENT-side: domcontentloaded fires before React
        // boots and the RootRoute guard navigates — poll the URL until the
        // SPA lands, then pin the login form (never a 404 fall-through).
        await expect.poll(() => page.url(), { timeout: 30000 }).toContain('/login');
        await expect(page.getByRole('button', { name: 'Login' })).toBeVisible();
      }
    });
  });
});
