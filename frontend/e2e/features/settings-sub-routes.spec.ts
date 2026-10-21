/**
 * E2E Feature: Settings sub-routes (close-test-coverage-gaps task 4.5).
 *
 * Routes under test (routes.tsx, /settings parent):
 *
 *   /settings/subscriptions  LineageSubscriptionsPage  any authenticated user;
 *                            `lineage.change_notifications` gates INSIDE the page
 *   /settings/subscription   SubscriptionPage          TENANT_ADMIN|PLATFORM_ADMIN
 *                            + CapabilityRoute "billing"
 *   /settings/delegation     DelegationSettingsPage    TENANT_ADMIN|PLATFORM_ADMIN
 *
 * Real backend only — no mocks, no stubs. Persona: e2e_admin (TENANT_ADMIN).
 * The delegation leg exercises the FULL UI CRUD against the real
 * /api/v1/governance/delegations/ API (shipped with this task — the page's
 * endpoints previously 404'd), including the real classified validation
 * errors. The lineage leg seeds a REAL contract + subscription via API and
 * mutates them through the REAL UI controls (severity PATCH, row DELETE).
 * The billing leg pins the seeded E2E plan contract (ensureE2eSubscription
 * idempotent prime).
 *
 * W16 environment policy: no bare skips anywhere in this file.
 */
import { expect, test } from '@playwright/test';

import {
  getComplianceOfficerUser,
  getTenantAdminUser,
  loginUser,
  loginViaApi,
  type TestUser,
} from '../fixtures/auth';
import { getApiBaseUrl } from '../fixtures/api-base';
import { ensureE2eSubscription } from '../fixtures/ensureE2eSubscription';
import { createODCSContractViaApi } from '../fixtures/api-assets';

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function plusDaysIso(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

async function getAccessToken(page: import('@playwright/test').Page): Promise<string | null> {
  return page.evaluate(() => {
    const g = (window as unknown as { __getAccessToken?: () => string | null })
      .__getAccessToken;
    return (typeof g === 'function' ? g() : null) ?? localStorage.getItem('access_token');
  });
}

async function apiAuthHeaders(user: TestUser): Promise<Record<string, string>> {
  const apiAuth = await loginViaApi(user.email, user.password);
  return {
    Authorization: `Bearer ${apiAuth.access_token}`,
    'Content-Type': 'application/json',
    ...(apiAuth.tenantId ? { 'X-Tenant-Id': apiAuth.tenantId } : {}),
  };
}

/**
 * Self-healing pre-clean: revoke every existing delegation for the tenant
 * through the REAL API. This spec is the only writer of delegation rows,
 * but a crashed earlier run must not leak an overlapping window (the
 * model's clean() rejects overlapping delegator-delegate pairs).
 */
async function revokeAllDelegations(
  page: import('@playwright/test').Page,
  user: TestUser,
): Promise<void> {
  const headers = await apiAuthHeaders(user);
  const listUrl = `${getApiBaseUrl()}/governance/delegations/`;
  const list = await page.request.get(listUrl, { headers });
  expect(list.ok(), `delegation pre-clean list failed: ${list.status()}`).toBeTruthy();
  const body = (await list.json()) as { results?: Array<{ id: string }> };
  for (const row of body.results ?? []) {
    const del = await page.request.delete(`${listUrl}${row.id}/`, { headers });
    expect(del.ok(), `delegation pre-clean revoke failed: ${del.status()}`).toBeTruthy();
  }
}

/**
 * Seed a lineage subscription for the given contract via the REAL API.
 * A previous run may already hold one for the same source — the backend's
 * 409 carries the existing row id, which the spec reuses (no-op cleanly).
 */
async function seedLineageSubscription(
  page: import('@playwright/test').Page,
  user: TestUser,
  contractId: string,
): Promise<string> {
  const headers = await apiAuthHeaders(user);
  const resp = await page.request.post(`${getApiBaseUrl()}/lineage/subscriptions/`, {
    headers,
    data: {
      source_contract: contractId,
      severity_threshold: 'CRITICAL',
      in_app: true,
      email: false,
    },
  });
  if (resp.status() === 409) {
    const body = (await resp.json()) as { id?: string };
    if (body.id) return body.id;
  }
  expect(
    resp.ok(),
    `lineage subscription seed failed: ${resp.status()} ${await resp.text()}`
  ).toBeTruthy();
  const body = (await resp.json()) as { id: string };
  return body.id;
}

test.describe('Feature: Settings sub-routes', () => {
  test.setTimeout(240000);

  test('delegation route runs the real create → list → revoke lifecycle', async ({ page }) => {
    const ta = await getTenantAdminUser();
    const cpo = await getComplianceOfficerUser();
    await revokeAllDelegations(page, ta);

    await loginUser(page, ta);
    await page.goto('/settings/delegation');
    await expect(page.getByTestId('delegation-settings-page')).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole('heading', { name: 'Approval Delegation' })).toBeVisible();
    await expect(page.locator('.delegation-empty')).toHaveText('No active delegations.');

    await page.getByTestId('toggle-delegation-form').click();
    const form = page.getByTestId('delegation-form');
    await expect(form).toBeVisible();
    await form.locator('#delegate-email').fill(cpo.email);
    await form.locator('#start-date').fill(todayIso());
    await form.locator('#end-date').fill(plusDaysIso(7));
    await form.getByRole('button', { name: 'Create Delegation' }).click();

    await expect(page.locator('.delegation-success')).toHaveText(
      'Delegation created successfully.'
    );
    const row = page.locator('[data-testid^="delegation-row-"]');
    await expect(row).toBeVisible();
    await expect(row).toContainText(cpo.email);
    await expect(row.locator('.delegation-status')).toHaveText('Active');

    const rowTestId = await row.getAttribute('data-testid');
    const rowId = (rowTestId ?? 'delegation-row-').replace('delegation-row-', '');
    await page.getByTestId(`revoke-delegation-${rowId}`).click();
    await expect(page.locator('.delegation-empty')).toBeVisible({ timeout: 30000 });
  });

  test('delegation form surfaces the real validation errors', async ({ page }) => {
    const ta = await getTenantAdminUser();
    const cpo = await getComplianceOfficerUser();
    await revokeAllDelegations(page, ta);

    await loginUser(page, ta);
    await page.goto('/settings/delegation');
    await page.getByTestId('toggle-delegation-form').click();
    const form = page.getByTestId('delegation-form');
    await expect(form).toBeVisible();

    // Client-side: end must be after start.
    await form.locator('#delegate-email').fill(cpo.email);
    await form.locator('#start-date').fill(plusDaysIso(2));
    await form.locator('#end-date').fill(plusDaysIso(1));
    await form.getByRole('button', { name: 'Create Delegation' }).click();
    await expect(page.locator('.delegation-form-error')).toHaveText(
      'End date must be after start date.'
    );

    // Server-side: the delegate must be an active user of the tenant —
    // the REAL classified 400 body.detail rides into the form error.
    await form.locator('#start-date').fill(todayIso());
    await form.locator('#end-date').fill(plusDaysIso(7));
    await form.locator('#delegate-email').fill('ghost-4p5@example.com');
    await form.getByRole('button', { name: 'Create Delegation' }).click();
    await expect(page.locator('.delegation-form-error')).toContainText('active user');
  });

  test('lineage subscriptions render a real seeded row and UI mutations persist', async ({
    page,
  }) => {
    const ta = await getTenantAdminUser();
    const contractId = await createODCSContractViaApi(ta);
    const subId = await seedLineageSubscription(page, ta, contractId);

    await loginUser(page, ta);
    await page.goto('/settings/subscriptions');
    await expect(page.getByTestId('lineage-subscriptions-page')).toBeVisible({
      timeout: 30000,
    });

    const row = page.getByTestId(`lineage-subscription-row-${subId}`);
    await expect(row).toBeVisible();
    await expect(row.getByLabel(/Severity threshold/)).toHaveValue('CRITICAL');

    // Real PATCH through the UI: severity bump + Save.
    const severity = row.getByLabel(/Severity threshold/);
    await severity.selectOption('HIGH');
    await row.getByTestId(`lineage-subscription-save-${subId}`).click();
    await expect(row.getByLabel(/Severity threshold/)).toHaveValue('HIGH');
    await expect(row.getByTestId(`lineage-subscription-save-${subId}`)).toBeDisabled();

    // Real DELETE through the UI → the honest empty state returns.
    await row.getByTestId(`lineage-subscription-delete-${subId}`).click();
    await expect(page.getByTestId('lineage-subscriptions-empty')).toBeVisible({
      timeout: 30000,
    });
  });

  test('billing subscription route renders the seeded E2E plan contract', async ({ page }) => {
    const ta = await getTenantAdminUser();
    await loginUser(page, ta);
    const accessToken = await getAccessToken(page);
    await ensureE2eSubscription(page, accessToken ?? '');

    await page.goto('/settings/subscription');
    await expect(page.locator('.subscription-page')).toBeVisible({ timeout: 30000 });
    await expect(page.locator('#subscription-plan-heading')).toBeVisible();
    // The E2E tenant's seeded subscription is ACTIVE — the status badge is
    // the pinned contract (the plan name is seeding-owned, not product logic).
    await expect(page.locator('.subscription-status-active')).toBeVisible();
    await expect(page.locator('#subscription-limits-heading')).toBeVisible();
    await expect(page.locator('#subscription-invoices-heading')).toBeVisible();
    // Invoice history is a table or the honest no-data state — never an
    // error surface.
    await expect(
      page.locator('.subscription-invoices-table, .subscription-no-data').first()
    ).toBeVisible();
  });
});
