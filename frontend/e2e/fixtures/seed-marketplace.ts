/**
 * seedMarketplaceListings — ensures ≥N published listings exist for the
 * current test tenant so comparison, trust-signal, saved-search, and
 * quick-preview E2E specs can assert against real data rather than skip.
 *
 * Always creates fresh listings because the API count query can include
 * listings from other tenants (cross-tenant visibility), but the browser
 * page filters by ``effectiveTenantId``.
 *
 * Also pre-grants ``marketplace.access`` consent for both the DPO and
 * consumer users so purchase/order tests don't hit CONSENT_REQUIRED.
 */
import type { TestUser } from './auth';
import { getConsumerTestUser, getTestUser, loginViaApi } from './auth';
import { createAssetViaApi, createDatasetViaApi } from './api-assets';
import { createListingViaApi, publishListingViaApi } from './api-marketplace';

const API_BASE = process.env.E2E_API_BASE_URL || 'http://localhost:8001/api/v1';
const SEED_RETRIES = 3;

async function countPublishedListings(token: string): Promise<number> {
  const res = await fetch(`${API_BASE}/marketplace/listings/?status=PUBLISHED&page_size=1`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return 0;
  const data = (await res.json()) as { count?: number };
  return data.count ?? 0;
}

async function grantConsentForUser(token: string, label: string): Promise<boolean> {
  const purposesResp = await fetch(`${API_BASE}/governance/consent-purposes/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!purposesResp.ok) {
    console.log(`[seed-marketplace] ${label}: purposes lookup returned ${purposesResp.status}`);
    return false;
  }
  const data = (await purposesResp.json()) as {
    results?: Array<{ id: string; key: string }>;
  };
  const purpose = (data.results ?? []).find((p) => p.key === 'marketplace.access');
  if (!purpose) {
    console.log(`[seed-marketplace] ${label}: marketplace.access purpose not found`);
    return false;
  }
  const grantResp = await fetch(`${API_BASE}/governance/consent-records/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ purpose_id: purpose.id, payload: { source: 'e2e-seed' } }),
  });
  const ok = grantResp.ok || grantResp.status === 409;
  console.log(`[seed-marketplace] ${label}: consent grant ${ok ? 'OK' : `returned ${grantResp.status}`}`);
  return ok;
}

export async function seedMarketplaceListings(
  minCount: number = 3,
  user?: TestUser,
): Promise<number> {
  const u = user ?? (await getTestUser());
  const auth = await loginViaApi(u.email, u.password);
  const token = auth.access_token;

  // Grant marketplace consent for the DPO user.
  await grantConsentForUser(token, 'DPO');

  // Grant marketplace consent + ensure subscription for the consumer user
  // (needed for purchase tests like UC-MKT-LINEAGE-002).
  try {
    const consumer = await getConsumerTestUser();
    const consumerAuth = await loginViaApi(consumer.email, consumer.password);
    // Ensure the consumer's tenant has an active subscription.  The
    // endpoint requires the X-E2E-Token shared secret in addition to
    // the Bearer token.
    const e2eToken = process.env.E2E_TEST_SECRET || '';
    const subHeaders: Record<string, string> = {
      Authorization: `Bearer ${consumerAuth.access_token}`,
    };
    if (e2eToken) subHeaders['X-E2E-Token'] = e2eToken;
    const subResp = await fetch(`${API_BASE}/test/ensure-e2e-subscription/`, {
      method: 'POST',
      headers: subHeaders,
    });
    console.log(`[seed-marketplace] consumer subscription ensure: ${subResp.ok ? 'OK' : subResp.status}`);
    await grantConsentForUser(consumerAuth.access_token, 'consumer');
  } catch (err) {
    console.log(`[seed-marketplace] consumer setup skipped: ${String(err).slice(0, 150)}`);
  }

  const apiCount = await countPublishedListings(token);
  console.log(`[seed-marketplace] API reports ${apiCount} published, need ≥${minCount}`);

  // Always create fresh listings so the browser page (filtered by
  // effectiveTenantId) has listings, regardless of API count accuracy.
  // The first listing also gets a dataset with sample data so the
  // trust-signals "sample indicator" test has something to assert on.
  let created = 0;
  let sampleDatasetCreated = false;
  for (let i = 0; i < minCount; i++) {
    let lastErr: unknown = null;
    for (let attempt = 0; attempt < SEED_RETRIES; attempt++) {
      try {
        const assetId = await createAssetViaApi(u, { forceNew: true, ensureActivated: true });
        // Attach a dataset with sample data to the first listing's asset.
        if (!sampleDatasetCreated) {
          try {
            const datasetId = await createDatasetViaApi(u, { assetId, forceNew: true });
            // PATCH the dataset to include sample_data_json so the backend
            // serializer's get_sample_available returns true.
            await fetch(`${API_BASE}/datasets/${datasetId}/`, {
              method: 'PATCH',
              headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}`,
              },
              body: JSON.stringify({ sample_data_json: { rows: 10, columns: ['id', 'name'] } }),
            });
            sampleDatasetCreated = true;
            console.log(`[seed-marketplace] sample dataset ${datasetId} created for asset ${assetId}`);
          } catch (err) {
            console.log(`[seed-marketplace] sample dataset skipped: ${String(err).slice(0, 150)}`);
          }
        }
        const listingId = await createListingViaApi(u, assetId, {
          title: `E2E Seed Listing ${Date.now()}-${i}`,
          pricingModel: 'FREE_AUTO_APPROVE',
        });
        await publishListingViaApi(u, listingId);
        created++;
        break;
      } catch (err) {
        lastErr = err;
        if (attempt < SEED_RETRIES - 1) await new Promise((r) => setTimeout(r, 2000));
      }
    }
    if (lastErr && created <= i) {
      console.log(`[seed-marketplace] listing ${i} failed after ${SEED_RETRIES} attempts: ${String(lastErr).slice(0, 200)}`);
    }
  }

  const final = await countPublishedListings(token);
  console.log(`[seed-marketplace] seed done: ${created} created, ${final} total`);
  return final;
}
