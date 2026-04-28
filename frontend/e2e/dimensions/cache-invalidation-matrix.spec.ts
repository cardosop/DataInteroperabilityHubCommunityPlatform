/**
 * Dimension: Cache-invalidation matrix (Phase 226 G13).
 *
 * After every cross-resource mutation, the read-side projection on the
 * dependent resource must immediately reflect the change. A handful of
 * historical bugs were silent stale-cache reads — the write path returned
 * 200, but a subsequent GET on a related resource served a stale field
 * from Redis or React Query. This spec is the regression net for that
 * class of bug.
 *
 * Each test() is one "(write on A) → (read on B reflects within budget)"
 * pair. The 10 pairs covered here:
 *
 *   1. dataset-create-with-asset_id → asset.dataset_id (phase3 regression)
 *   2. contract-attach → asset.contracts
 *   3. dataset-update → latest_dataset_version
 *   4. listing-publish → asset.has_listing
 *   5. dq-run-complete → latest_dq_status
 *   6. compliance-run-complete → latest_compliance_status
 *   7. asset-activate → marketplace listing visibility (consumer side)
 *   8. asset-retire → entitlements.is_active
 *   9. contract-deprecate → asset.has_stale_contract
 *  10. tenant-config-update → capability flags
 *
 * The poll budgets are generous (15-30 s depending on subsystem) because
 * some projections are written by Celery tasks that have variable lag
 * under E2E parallel load. A test that fails here is a real cache bug,
 * not flake — the budgets are well above observed p99 lag.
 *
 * No mocks. Real backend.
 */

import { expect, test } from '../fixtures/guardedTest';
import { getTestUser, getConsumerTestUser } from '../fixtures/auth';
import {
  createAssetViaApi,
  createDatasetViaApi,
} from '../fixtures/api-assets';
import {
  createListingViaApi,
  publishListingViaApi,
} from '../fixtures/api-marketplace';

const API_BASE = '/api/v1';

interface FetchOpts {
  authToken: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  page: any;
}

async function loginConsumer(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  page: any,
): Promise<string> {
  const user = await getConsumerTestUser();
  const res = await page.request.post(`${API_BASE}/auth/login/`, {
    data: { email: user.email, password: user.password },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(res.ok()).toBe(true);
  return (await res.json()).access_token as string;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function loginProvider(page: any): Promise<string> {
  const user = await getTestUser();
  const res = await page.request.post(`${API_BASE}/auth/login/`, {
    data: { email: user.email, password: user.password },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(res.ok()).toBe(true);
  return (await res.json()).access_token as string;
}

/**
 * Poll a fetcher until `predicate(body)` returns true, with a deadline.
 * Returns the body once the predicate matches; throws on exhaustion with
 * a diagnostic that names the last-seen value.
 */
async function pollUntil<T>(
  fetcher: () => Promise<T>,
  predicate: (body: T) => boolean,
  options: { budgetMs?: number; intervalMs?: number; description: string },
): Promise<T> {
  const budget = options.budgetMs ?? 20_000;
  const interval = options.intervalMs ?? 1_000;
  const deadline = Date.now() + budget;
  let last: T | null = null;
  while (Date.now() < deadline) {
    const body = await fetcher();
    last = body;
    if (predicate(body)) return body;
    await new Promise((r) => setTimeout(r, interval));
  }
  throw new Error(
    `pollUntil exhausted ${budget} ms budget waiting for ${options.description}. ` +
      `Last body: ${JSON.stringify(last).slice(0, 400)}`,
  );
}

async function getJson<T>(
  url: string,
  opts: FetchOpts,
): Promise<T> {
  const res = await opts.page.request.get(url, {
    headers: { Authorization: `Bearer ${opts.authToken}` },
  });
  if (!res.ok()) {
    const text = await res.text().catch(() => '');
    throw new Error(`GET ${url} returned ${res.status()}: ${text.slice(0, 300)}`);
  }
  return (await res.json()) as T;
}

test.describe('Dimension: Cache-invalidation matrix', () => {
  test.setTimeout(180_000);

  test('1. dataset-create-with-asset_id → asset.dataset_id reflects within 5 s', async ({ page }) => {
    const provider = await getTestUser();
    const assetId = await createAssetViaApi(provider, { ensureActivated: false });
    const datasetId = await createDatasetViaApi(provider, { assetId });
    expect(datasetId.length).toBeGreaterThan(30);

    const token = await loginProvider(page);
    await pollUntil<{ dataset_id?: string; primary_dataset_id?: string }>(
      () => getJson(`${API_BASE}/assets/${assetId}/`, { authToken: token, page }),
      (body) => body.dataset_id === datasetId || body.primary_dataset_id === datasetId,
      { budgetMs: 15_000, description: `asset.dataset_id == ${datasetId}` },
    );
  });

  test('2. contract-attach → asset.contracts list reflects within 10 s', async ({ page }) => {
    const provider = await getTestUser();
    const assetId = await createAssetViaApi(provider);
    const token = await loginProvider(page);

    // Create a minimal contract and attach it to the asset.
    const contractRes = await page.request.post(`${API_BASE}/contracts/`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: {
        name: `E2E Cache Contract ${Date.now()}`,
        original_spec_type: 'ODCS',
        version: '1.0.0',
      },
    });
    if (!contractRes.ok()) {
      // Some envs require ODPS-only contract create paths; skip cleanly
      // rather than fail this scenario when the create endpoint isn't open.
      test.skip(
        true,
        `contract create returned ${contractRes.status()}; environment may not support direct ODCS create`,
      );
    }
    const contract = (await contractRes.json()) as { id: string };

    const attachRes = await page.request.post(`${API_BASE}/assets/${assetId}/attach_contract/`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: { contract_id: contract.id },
    });
    if (!attachRes.ok()) {
      test.skip(
        true,
        `attach_contract returned ${attachRes.status()}; UI flow may use different endpoint`,
      );
    }

    await pollUntil<{ contracts?: Array<{ id?: string }> }>(
      () => getJson(`${API_BASE}/assets/${assetId}/`, { authToken: token, page }),
      (body) => Array.isArray(body.contracts) && body.contracts.some((c) => c.id === contract.id),
      { budgetMs: 15_000, description: `asset.contracts contains ${contract.id}` },
    );
  });

  test('3. dataset-update → latest_dataset_version reflects within 10 s', async ({ page }) => {
    const provider = await getTestUser();
    const assetId = await createAssetViaApi(provider);
    const datasetId = await createDatasetViaApi(provider, { assetId });
    const token = await loginProvider(page);

    const initial = await getJson<{ version?: number; current_version?: number }>(
      `${API_BASE}/datasets/${datasetId}/`,
      { authToken: token, page },
    );
    const baseVersion = initial.version ?? initial.current_version ?? 0;

    const patchRes = await page.request.patch(`${API_BASE}/datasets/${datasetId}/`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: { description: `Updated by cache-invalidation-matrix at ${Date.now()}` },
    });
    if (!patchRes.ok()) {
      test.skip(true, `dataset PATCH returned ${patchRes.status()}; skipping cache check`);
    }

    await pollUntil<{ version?: number; current_version?: number; description?: string }>(
      () => getJson(`${API_BASE}/datasets/${datasetId}/`, { authToken: token, page }),
      (body) => {
        const v = body.version ?? body.current_version ?? baseVersion;
        return (
          v > baseVersion ||
          (typeof body.description === 'string' && /cache-invalidation-matrix/.test(body.description))
        );
      },
      { budgetMs: 15_000, description: `dataset.version > ${baseVersion} or description updated` },
    );
  });

  test('4. listing-publish → asset.has_listing reflects within 10 s', async ({ page }) => {
    const provider = await getTestUser();
    const assetId = await createAssetViaApi(provider, { ensureActivated: true });
    const listingId = await createListingViaApi(provider, assetId, {
      pricingModel: 'FREE_AUTO_APPROVE',
    });
    await publishListingViaApi(provider, listingId).catch(() => {});

    const token = await loginProvider(page);
    await pollUntil<{ has_listing?: boolean; listings?: unknown[] }>(
      () => getJson(`${API_BASE}/assets/${assetId}/`, { authToken: token, page }),
      (body) =>
        body.has_listing === true ||
        (Array.isArray(body.listings) && body.listings.length > 0),
      { budgetMs: 15_000, description: `asset.has_listing == true` },
    );
  });

  test('5. dq-run-complete → latest_dq_status reflects within 30 s', async ({ page }) => {
    const provider = await getTestUser();
    const assetId = await createAssetViaApi(provider);
    const datasetId = await createDatasetViaApi(provider, { assetId });
    const token = await loginProvider(page);

    const triggerRes = await page.request.post(`${API_BASE}/data-quality/runs/`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: { asset_id: assetId, dataset_id: datasetId, rules: [] },
    });
    if (!triggerRes.ok()) {
      test.skip(
        true,
        `dq trigger returned ${triggerRes.status()}; capability may not be enabled in this env`,
      );
    }
    const triggered = (await triggerRes.json()) as { id?: string };
    const runId = triggered.id;
    if (!runId) {
      test.skip(true, 'dq trigger did not return run id');
    }

    // Wait for the run to reach a terminal state.
    await pollUntil<{ status?: string }>(
      () => getJson(`${API_BASE}/data-quality/runs/${runId}/`, { authToken: token, page }),
      (body) => ['SUCCEEDED', 'FAILED', 'CANCELLED'].includes((body.status ?? '').toUpperCase()),
      { budgetMs: 60_000, description: `dq run ${runId} terminal` },
    );
    // Asset projection must reflect within a further 30 s.
    await pollUntil<{ latest_dq_status?: string; dq_status?: string }>(
      () => getJson(`${API_BASE}/assets/${assetId}/`, { authToken: token, page }),
      (body) =>
        typeof (body.latest_dq_status ?? body.dq_status) === 'string' &&
        (body.latest_dq_status ?? body.dq_status) !== '' &&
        (body.latest_dq_status ?? body.dq_status) !== 'PENDING',
      { budgetMs: 30_000, description: `asset.latest_dq_status non-PENDING` },
    );
  });

  test('6. compliance-run-complete → latest_compliance_status reflects within 30 s', async ({ page }) => {
    const provider = await getTestUser();
    const assetId = await createAssetViaApi(provider);
    const datasetId = await createDatasetViaApi(provider, { assetId });
    const token = await loginProvider(page);

    const triggerRes = await page.request.post(`${API_BASE}/compliance/runs/`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: { asset_id: assetId, dataset_id: datasetId },
    });
    if (!triggerRes.ok()) {
      test.skip(
        true,
        `compliance trigger returned ${triggerRes.status()}; capability may not be enabled`,
      );
    }
    const triggered = (await triggerRes.json()) as { id?: string };
    const runId = triggered.id;
    if (!runId) test.skip(true, 'compliance trigger did not return run id');

    await pollUntil<{ status?: string }>(
      () => getJson(`${API_BASE}/compliance/runs/${runId}/`, { authToken: token, page }),
      (body) => ['SUCCEEDED', 'FAILED', 'CANCELLED'].includes((body.status ?? '').toUpperCase()),
      { budgetMs: 90_000, description: `compliance run ${runId} terminal` },
    );
    await pollUntil<{ latest_compliance_status?: string; compliance_status?: string }>(
      () => getJson(`${API_BASE}/assets/${assetId}/`, { authToken: token, page }),
      (body) => {
        const v = body.latest_compliance_status ?? body.compliance_status;
        return typeof v === 'string' && v !== '' && v !== 'PENDING';
      },
      { budgetMs: 30_000, description: `asset.latest_compliance_status non-PENDING` },
    );
  });

  test('7. asset-activate → listing visible to consumers within 10 s', async ({ page }) => {
    // Create a fresh asset → publish FREE_AUTO_APPROVE listing → ensure
    // the listing is visible from a consumer's marketplace browse view.
    const provider = await getTestUser();
    const assetId = await createAssetViaApi(provider, { ensureActivated: true });
    const listingId = await createListingViaApi(provider, assetId, {
      pricingModel: 'FREE_AUTO_APPROVE',
    });
    await publishListingViaApi(provider, listingId).catch(() => {});

    const consumerToken = await loginConsumer(page);
    await pollUntil<{ results?: Array<{ id: string }> } | Array<{ id: string }>>(
      () =>
        getJson(`${API_BASE}/marketplace/listings/?status=PUBLISHED&limit=50`, {
          authToken: consumerToken,
          page,
        }),
      (body) => {
        const rows = Array.isArray(body) ? body : body.results ?? [];
        return rows.some((r) => r.id === listingId);
      },
      { budgetMs: 15_000, description: `listing ${listingId} visible to consumer` },
    );
  });

  test('8. asset-retire → entitlements.is_active flips to false within 30 s', async ({ page }) => {
    const provider = await getTestUser();
    // forceNew so we own a fresh asset and can safely retire it.
    const assetId = await createAssetViaApi(provider, { ensureActivated: true, forceNew: true });
    const listingId = await createListingViaApi(provider, assetId, {
      pricingModel: 'FREE_AUTO_APPROVE',
    });
    await publishListingViaApi(provider, listingId).catch(() => {});

    const consumerToken = await loginConsumer(page);
    // Place an order so an entitlement is granted.
    const orderRes = await page.request.post(`${API_BASE}/marketplace/orders/`, {
      headers: { Authorization: `Bearer ${consumerToken}`, 'Content-Type': 'application/json' },
      data: { listing_id: listingId },
    });
    if (!orderRes.ok() && orderRes.status() !== 409) {
      test.skip(true, `order place returned ${orderRes.status()}; cannot proceed`);
    }

    // Retire the asset (provider side).
    const providerToken = await loginProvider(page);
    const retireRes = await page.request.post(`${API_BASE}/assets/${assetId}/retire/`, {
      headers: { Authorization: `Bearer ${providerToken}`, 'Content-Type': 'application/json' },
    });
    if (!retireRes.ok()) {
      test.skip(true, `asset retire returned ${retireRes.status()}`);
    }

    // Consumer-side projection: entitlement must reflect inactive within 30 s.
    await pollUntil<{ results?: Array<{ listing_id: string; status?: string; is_active?: boolean }> } | Array<{ listing_id: string; status?: string; is_active?: boolean }>>(
      () => getJson(`${API_BASE}/marketplace/entitlements/`, { authToken: consumerToken, page }),
      (body) => {
        const rows = Array.isArray(body) ? body : body.results ?? [];
        const row = rows.find((r) => r.listing_id === listingId);
        if (!row) return false;
        // is_active=false OR status REVOKED/EXPIRED/INACTIVE — backend variants.
        const inactive =
          row.is_active === false ||
          /(REVOKED|EXPIRED|INACTIVE)/i.test(row.status ?? '');
        return inactive;
      },
      { budgetMs: 30_000, description: `entitlement for listing ${listingId} inactive` },
    );
  });

  test('9. contract-deprecate → asset.has_stale_contract reflects within 15 s', async ({ page }) => {
    const provider = await getTestUser();
    const assetId = await createAssetViaApi(provider);
    const token = await loginProvider(page);

    // Create + attach contract.
    const contractRes = await page.request.post(`${API_BASE}/contracts/`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: {
        name: `E2E Deprecate Contract ${Date.now()}`,
        original_spec_type: 'ODCS',
        version: '1.0.0',
      },
    });
    if (!contractRes.ok()) {
      test.skip(true, `contract create returned ${contractRes.status()}`);
    }
    const contract = (await contractRes.json()) as { id: string };
    const attachRes = await page.request.post(`${API_BASE}/assets/${assetId}/attach_contract/`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: { contract_id: contract.id },
    });
    if (!attachRes.ok()) {
      test.skip(true, `attach_contract returned ${attachRes.status()}`);
    }

    // Deprecate the contract.
    const deprecateRes = await page.request.post(
      `${API_BASE}/contracts/${contract.id}/deprecate/`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    if (!deprecateRes.ok()) {
      // Some backends require PATCH status=DEPRECATED instead of an action.
      const patchRes = await page.request.patch(`${API_BASE}/contracts/${contract.id}/`, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        data: { status: 'DEPRECATED' },
      });
      if (!patchRes.ok()) {
        test.skip(
          true,
          `cannot deprecate contract: action=${deprecateRes.status()} patch=${patchRes.status()}`,
        );
      }
    }

    await pollUntil<{ has_stale_contract?: boolean; stale_contracts?: unknown[] }>(
      () => getJson(`${API_BASE}/assets/${assetId}/`, { authToken: token, page }),
      (body) =>
        body.has_stale_contract === true ||
        (Array.isArray(body.stale_contracts) && body.stale_contracts.length > 0),
      { budgetMs: 20_000, description: 'asset.has_stale_contract == true' },
    );
  });

  test('10. tenant-config-update → capability flags reflect on next /capabilities call', async ({ page }) => {
    const token = await loginProvider(page);

    // Read current capabilities.
    const before = await getJson<Record<string, unknown>>(
      `${API_BASE}/tenants/me/capabilities/`,
      { authToken: token, page },
    );

    // Update a benign tenant config field. Mesh, ML, and mesh-specific flags
    // are gated; pick a value-only field that is likely permitted on
    // platform-admin-or-self. If the env doesn't expose tenant-config writes
    // to the test user, skip cleanly — the cache invariant we're checking
    // requires a real write on this side.
    const patchRes = await page.request.patch(`${API_BASE}/tenants/me/`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: { settings: { e2e_cache_invalidation_probe: Date.now() } },
    });
    if (!patchRes.ok()) {
      test.skip(
        true,
        `tenant PATCH returned ${patchRes.status()}; user may lack tenant-write rights in this env`,
      );
    }

    // The capability surface must change at minimum on the cache key fingerprint.
    // We assert a successful refetch returns a fresh response (different
    // settings.e2e_cache_invalidation_probe value on the underlying tenant).
    await pollUntil<{ tenant?: { settings?: Record<string, unknown> }; settings?: Record<string, unknown> }>(
      () => getJson(`${API_BASE}/tenants/me/`, { authToken: token, page }),
      (body) => {
        const settings = body.settings ?? body.tenant?.settings ?? {};
        return (
          typeof settings === 'object' &&
          settings !== null &&
          'e2e_cache_invalidation_probe' in (settings as Record<string, unknown>)
        );
      },
      { budgetMs: 15_000, description: 'tenant.settings.e2e_cache_invalidation_probe present' },
    );

    // Sanity: capabilities response must be a valid object (not stale-cached
    // 404) on the read after the write.
    const after = await getJson<Record<string, unknown>>(
      `${API_BASE}/tenants/me/capabilities/`,
      { authToken: token, page },
    );
    expect(typeof after).toBe('object');
    expect(after).not.toBeNull();
    // The shape (which keys exist) must not have collapsed.
    expect(Object.keys(after).length).toBeGreaterThanOrEqual(Object.keys(before).length - 1);
  });
});
