/**
 * Dimension: Tenant-isolation matrix (Phase 226 G14).
 *
 * For every resource family that lives behind a tenant scope, we assert
 * that resources created in tenant A return 404 (not 403, not 200) when
 * fetched from tenant B's session. 404 is the contractual signal — 403
 * would leak existence; 200 is a security incident.
 *
 * Resource families covered:
 *   1. Asset
 *   2. Dataset
 *   3. Contract
 *   4. Listing
 *   5. DQ run
 *   6. Compliance run
 *   7. Audit event
 *   8. Webhook
 *   9. Entitlement
 *  10. Scheduled ingestion / export (combined family — same isolation rule)
 *
 * Uses `disposableTenantTest` so each scenario gets two fresh tenants
 * with no leakage from prior runs. Resources that fail to provision in
 * tenant A skip with a clear annotation rather than failing — capability
 * gating is environment-dependent, but tenant isolation MUST hold in
 * every environment that supports a given resource at all.
 *
 * No mocks. Real backend.
 */

import { expect } from '@playwright/test';
import { disposableTenantTest as test } from '../fixtures/disposableTenant';
import { verifyViaApiAbsent } from '../fixtures/verifyViaApi';

const API_BASE = '/api/v1';

interface AuthCtx {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  page: any;
  token: string;
}

async function login(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  page: any,
  email: string,
  password: string,
): Promise<string> {
  const res = await page.request.post(`${API_BASE}/auth/login/`, {
    data: { email, password },
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok()) {
    throw new Error(
      `login for ${email} returned ${res.status()}: ${(await res.text()).slice(0, 200)}`,
    );
  }
  return (await res.json()).access_token as string;
}

/**
 * Inject the bearer header into the page's localStorage so the
 * verifyViaApiAbsent helper (which reads from localStorage) authenticates
 * as tenant B's user. Returns a function that restores the previous token.
 */
async function asTenantB(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  page: any,
  tokenB: string,
): Promise<() => Promise<void>> {
  // page.goto a same-origin route so localStorage is accessible.
  await page.goto('/login', { waitUntil: 'domcontentloaded' });
  const previous = await page.evaluate(() => localStorage.getItem('access_token'));
  await page.evaluate((token: string) => localStorage.setItem('access_token', token), tokenB);
  return async () => {
    await page.evaluate(
      ([prev]: [string | null]) => {
        if (prev === null) localStorage.removeItem('access_token');
        else localStorage.setItem('access_token', prev);
      },
      [previous],
    );
  };
}

interface CreateResult<T extends object = Record<string, unknown>> {
  ok: boolean;
  status: number;
  body: T | null;
}

async function postAs<T extends object = Record<string, unknown>>(
  ctx: AuthCtx,
  path: string,
  data: Record<string, unknown>,
): Promise<CreateResult<T>> {
  const res = await ctx.page.request.post(`${API_BASE}${path}`, {
    headers: {
      Authorization: `Bearer ${ctx.token}`,
      'Content-Type': 'application/json',
    },
    data,
  });
  const ok = res.ok();
  let body: T | null = null;
  try {
    body = (await res.json()) as T;
  } catch {
    /* no body */
  }
  return { ok, status: res.status(), body };
}

test.describe('Dimension: Tenant-isolation matrix', () => {
  test.setTimeout(180_000);

  test('1. asset created in tenant A is 404 in tenant B', async ({ page, tenantA, tenantB }) => {
    const tokenA = await login(page, tenantA.admin.email, tenantA.admin.password);
    const created = await postAs<{ id: string }>(
      { page, token: tokenA },
      '/assets/',
      {
        key: `e2e-iso-asset-${Date.now()}`,
        name: 'Tenant Isolation Asset',
        visibility: 'INTERNAL',
      },
    );
    if (!created.ok) test.skip(true, `asset create in tenant A failed: ${created.status}`);
    const assetId = created.body!.id;

    const tokenB = await login(page, tenantB.admin.email, tenantB.admin.password);
    const restore = await asTenantB(page, tokenB);
    try {
      await verifyViaApiAbsent(page, `${API_BASE}/assets/${assetId}/`);
    } finally {
      await restore();
    }
  });

  test('2. dataset created in tenant A is 404 in tenant B', async ({ page, tenantA, tenantB }) => {
    const tokenA = await login(page, tenantA.admin.email, tenantA.admin.password);
    const asset = await postAs<{ id: string }>(
      { page, token: tokenA },
      '/assets/',
      { key: `e2e-iso-ds-${Date.now()}`, name: 'Iso DS Asset', visibility: 'INTERNAL' },
    );
    if (!asset.ok) test.skip(true, `asset precond failed: ${asset.status}`);
    const dataset = await postAs<{ id: string }>(
      { page, token: tokenA },
      '/datasets/',
      {
        asset_id: asset.body!.id,
        name: `Iso DS ${Date.now()}`,
      },
    );
    if (!dataset.ok) test.skip(true, `dataset create failed: ${dataset.status}`);

    const tokenB = await login(page, tenantB.admin.email, tenantB.admin.password);
    const restore = await asTenantB(page, tokenB);
    try {
      await verifyViaApiAbsent(page, `${API_BASE}/datasets/${dataset.body!.id}/`);
    } finally {
      await restore();
    }
  });

  test('3. contract created in tenant A is 404 in tenant B', async ({ page, tenantA, tenantB }) => {
    const tokenA = await login(page, tenantA.admin.email, tenantA.admin.password);
    const contract = await postAs<{ id: string }>(
      { page, token: tokenA },
      '/contracts/',
      {
        name: `Iso Contract ${Date.now()}`,
        original_spec_type: 'ODCS',
        version: '1.0.0',
      },
    );
    if (!contract.ok) test.skip(true, `contract create failed: ${contract.status}`);

    const tokenB = await login(page, tenantB.admin.email, tenantB.admin.password);
    const restore = await asTenantB(page, tokenB);
    try {
      await verifyViaApiAbsent(page, `${API_BASE}/contracts/${contract.body!.id}/`);
    } finally {
      await restore();
    }
  });

  test('4. marketplace listing created in tenant A is 404 in tenant B', async ({ page, tenantA, tenantB }) => {
    const tokenA = await login(page, tenantA.admin.email, tenantA.admin.password);
    const asset = await postAs<{ id: string }>(
      { page, token: tokenA },
      '/assets/',
      { key: `e2e-iso-listing-${Date.now()}`, name: 'Iso Listing Asset', visibility: 'INTERNAL' },
    );
    if (!asset.ok) test.skip(true, `asset precond failed: ${asset.status}`);
    // Activate before listing.
    await postAs({ page, token: tokenA }, `/assets/${asset.body!.id}/activate/`, {});
    const listing = await postAs<{ id: string }>(
      { page, token: tokenA },
      '/marketplace/listings/',
      {
        asset_id: asset.body!.id,
        title: `Iso Listing ${Date.now()}`,
        short_description: 'Iso',
        pricing_model: 'FREE_AUTO_APPROVE',
        price_amount: 0.0,
      },
    );
    if (!listing.ok) test.skip(true, `listing create failed: ${listing.status}`);

    const tokenB = await login(page, tenantB.admin.email, tenantB.admin.password);
    const restore = await asTenantB(page, tokenB);
    try {
      await verifyViaApiAbsent(page, `${API_BASE}/marketplace/listings/${listing.body!.id}/`);
    } finally {
      await restore();
    }
  });

  test('5. DQ run created in tenant A is 404 in tenant B', async ({ page, tenantA, tenantB }) => {
    const tokenA = await login(page, tenantA.admin.email, tenantA.admin.password);
    const asset = await postAs<{ id: string }>(
      { page, token: tokenA },
      '/assets/',
      { key: `e2e-iso-dq-${Date.now()}`, name: 'Iso DQ Asset', visibility: 'INTERNAL' },
    );
    if (!asset.ok) test.skip(true, `asset precond failed: ${asset.status}`);
    const run = await postAs<{ id: string }>(
      { page, token: tokenA },
      '/data-quality/runs/',
      { asset_id: asset.body!.id, rules: [] },
    );
    if (!run.ok) test.skip(true, `dq run create failed: ${run.status}`);

    const tokenB = await login(page, tenantB.admin.email, tenantB.admin.password);
    const restore = await asTenantB(page, tokenB);
    try {
      await verifyViaApiAbsent(page, `${API_BASE}/data-quality/runs/${run.body!.id}/`);
    } finally {
      await restore();
    }
  });

  test('6. compliance run created in tenant A is 404 in tenant B', async ({ page, tenantA, tenantB }) => {
    const tokenA = await login(page, tenantA.admin.email, tenantA.admin.password);
    const asset = await postAs<{ id: string }>(
      { page, token: tokenA },
      '/assets/',
      { key: `e2e-iso-comp-${Date.now()}`, name: 'Iso Comp Asset', visibility: 'INTERNAL' },
    );
    if (!asset.ok) test.skip(true, `asset precond failed: ${asset.status}`);
    const run = await postAs<{ id: string }>(
      { page, token: tokenA },
      '/compliance/runs/',
      { asset_id: asset.body!.id },
    );
    if (!run.ok) test.skip(true, `compliance run create failed: ${run.status}`);

    const tokenB = await login(page, tenantB.admin.email, tenantB.admin.password);
    const restore = await asTenantB(page, tokenB);
    try {
      await verifyViaApiAbsent(page, `${API_BASE}/compliance/runs/${run.body!.id}/`);
    } finally {
      await restore();
    }
  });

  test('7. audit event in tenant A is 404 in tenant B', async ({ page, tenantA, tenantB }) => {
    // Create an asset in tenant A to generate an audit event we can target.
    const tokenA = await login(page, tenantA.admin.email, tenantA.admin.password);
    const asset = await postAs<{ id: string }>(
      { page, token: tokenA },
      '/assets/',
      { key: `e2e-iso-audit-${Date.now()}`, name: 'Iso Audit Asset', visibility: 'INTERNAL' },
    );
    if (!asset.ok) test.skip(true, `asset precond failed: ${asset.status}`);

    // Find the audit row via list endpoint.
    const auditList = await page.request.get(
      `${API_BASE}/audit/audit-events/?resource_id=${asset.body!.id}&page_size=5`,
      { headers: { Authorization: `Bearer ${tokenA}` } },
    );
    if (!auditList.ok()) test.skip(true, `audit list failed in tenant A: ${auditList.status()}`);
    const listBody = (await auditList.json()) as { results?: Array<{ id: string }> };
    const auditId = listBody.results?.[0]?.id;
    if (!auditId) test.skip(true, 'no audit event to compare across tenants');

    const tokenB = await login(page, tenantB.admin.email, tenantB.admin.password);
    const restore = await asTenantB(page, tokenB);
    try {
      // Tenant B asks for the audit row directly. Tenant scope filter on
      // AuditEventViewSet must hide it as 404. (Tenant admin in B without
      // platform_admin role cannot see other tenants' audit events.)
      await verifyViaApiAbsent(page, `${API_BASE}/audit/audit-events/${auditId}/`);
    } finally {
      await restore();
    }
  });

  test('8. webhook configured in tenant A is 404 in tenant B', async ({ page, tenantA, tenantB }) => {
    const tokenA = await login(page, tenantA.admin.email, tenantA.admin.password);
    const webhook = await postAs<{ id: string }>(
      { page, token: tokenA },
      '/webhooks/',
      {
        name: `Iso Webhook ${Date.now()}`,
        target_url: 'https://example.invalid/webhook',
        events: ['asset.created'],
        active: true,
      },
    );
    if (!webhook.ok) test.skip(true, `webhook create failed: ${webhook.status}`);

    const tokenB = await login(page, tenantB.admin.email, tenantB.admin.password);
    const restore = await asTenantB(page, tokenB);
    try {
      await verifyViaApiAbsent(page, `${API_BASE}/webhooks/${webhook.body!.id}/`);
    } finally {
      await restore();
    }
  });

  test('9. entitlement granted in tenant A is 404 in tenant B', async ({ page, tenantA, tenantB }) => {
    // Provider+consumer same tenant (FREE_AUTO_APPROVE in tenant A).
    const tokenA = await login(page, tenantA.admin.email, tenantA.admin.password);
    const asset = await postAs<{ id: string }>(
      { page, token: tokenA },
      '/assets/',
      { key: `e2e-iso-ent-${Date.now()}`, name: 'Iso Ent Asset', visibility: 'INTERNAL' },
    );
    if (!asset.ok) test.skip(true, `asset precond failed: ${asset.status}`);
    await postAs({ page, token: tokenA }, `/assets/${asset.body!.id}/activate/`, {});
    const listing = await postAs<{ id: string }>(
      { page, token: tokenA },
      '/marketplace/listings/',
      {
        asset_id: asset.body!.id,
        title: `Iso Ent Listing ${Date.now()}`,
        short_description: 'Iso',
        pricing_model: 'FREE_AUTO_APPROVE',
        price_amount: 0.0,
      },
    );
    if (!listing.ok) test.skip(true, `listing create failed: ${listing.status}`);

    const orderRes = await postAs<{ id?: string; order?: { id?: string }; entitlement?: { id: string } }>(
      { page, token: tokenA },
      '/marketplace/orders/',
      { listing_id: listing.body!.id },
    );
    if (!orderRes.ok) test.skip(true, `order create failed: ${orderRes.status}`);
    const entitlementId = orderRes.body!.entitlement?.id;
    if (!entitlementId) {
      test.skip(true, 'order response did not include entitlement id (auto-approve may not have fulfilled in time)');
    }

    const tokenB = await login(page, tenantB.admin.email, tenantB.admin.password);
    const restore = await asTenantB(page, tokenB);
    try {
      await verifyViaApiAbsent(page, `${API_BASE}/marketplace/entitlements/${entitlementId}/`);
    } finally {
      await restore();
    }
  });

  test('10. scheduled ingestion / export in tenant A is 404 in tenant B', async ({
    page,
    tenantA,
    tenantB,
  }) => {
    const tokenA = await login(page, tenantA.admin.email, tenantA.admin.password);
    // Try ingestion first (more universally enabled). Fall back to scheduled
    // export if ingestion is gated. Either resource family must obey
    // tenant-scope isolation.
    const ingest = await postAs<{ id: string }>(
      { page, token: tokenA },
      '/scheduled-ingestion/configs/',
      {
        name: `Iso Ingest ${Date.now()}`,
        source_type: 'CSV_HTTP',
        source_config: { url: 'https://example.invalid/feed.csv' },
        schedule_cron: '0 0 * * *',
        is_enabled: false,
      },
    );
    let kind: 'ingestion' | 'export' = 'ingestion';
    let resourceId: string | undefined = ingest.body?.id;
    let endpointBase = '/scheduled-ingestion/configs/';

    if (!ingest.ok || !resourceId) {
      const exportRes = await postAs<{ id: string }>(
        { page, token: tokenA },
        '/scheduled-export/configs/',
        {
          name: `Iso Export ${Date.now()}`,
          destination_type: 'S3',
          destination_config: { bucket: 'example-invalid' },
          schedule_cron: '0 0 * * *',
          is_enabled: false,
        },
      );
      if (!exportRes.ok || !exportRes.body?.id) {
        test.skip(
          true,
          `neither scheduled-ingestion nor scheduled-export create succeeded ` +
            `(${ingest.status}/${exportRes.status})`,
        );
      }
      kind = 'export';
      resourceId = exportRes.body!.id;
      endpointBase = '/scheduled-export/configs/';
    }
    expect(['ingestion', 'export']).toContain(kind);

    const tokenB = await login(page, tenantB.admin.email, tenantB.admin.password);
    const restore = await asTenantB(page, tokenB);
    try {
      await verifyViaApiAbsent(page, `${API_BASE}${endpointBase}${resourceId}/`);
    } finally {
      await restore();
    }
  });
});
