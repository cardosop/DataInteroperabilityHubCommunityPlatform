/**
 * E2E API helpers for marketplace operations (listing, order, entitlement management).
 * Follows the same pattern as api-assets.ts — real backend only, no mocks.
 */

import type { TestUser } from '../setup/create-test-user';

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
  listing_id: string;
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
    const body = await resp.text().catch(() => '');
    throw new Error(`createListingViaApi failed: ${resp.status} ${body}`);
  }
  const data = (await resp.json()) as { id?: string };
  if (!data.id) throw new Error('createListingViaApi: response missing id');
  return data.id;
}

/**
 * Publish a draft listing.
 * Tries PATCH /marketplace/listings/{id}/ with status=PUBLISHED,
 * then POST /marketplace/listings/{id}/publish/ as fallback.
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

  // Try PATCH status first
  const patchResp = await fetch(`${API_BASE_URL}/marketplace/listings/${listingId}/`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify({ status: 'PUBLISHED' }),
  });
  if (patchResp.ok) return;

  // Fallback: POST /publish/
  const publishResp = await fetch(
    `${API_BASE_URL}/marketplace/listings/${listingId}/publish/`,
    { method: 'POST', headers }
  );
  if (!publishResp.ok) {
    const body = await publishResp.text().catch(() => '');
    throw new Error(`publishListingViaApi failed: ${publishResp.status} ${body}`);
  }
}

/**
 * Place an order for a listing. Calls POST /marketplace/orders/.
 * Returns the order ID.
 */
export async function placeOrderViaApi(
  consumerUser: TestUser,
  listingId: string
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
    const body = await resp.text().catch(() => '');
    throw new Error(`placeOrderViaApi failed: ${resp.status} ${body}`);
  }
  const data = (await resp.json()) as { id?: string; order?: { id?: string } };
  const orderId = data.id || data.order?.id;
  if (!orderId) throw new Error('placeOrderViaApi: response missing order id');
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
    const body = await resp.text().catch(() => '');
    throw new Error(`getEntitlementsViaApi failed: ${resp.status} ${body}`);
  }
  const data = (await resp.json()) as
    | { results?: MarketplaceEntitlement[] }
    | MarketplaceEntitlement[];
  return Array.isArray(data) ? data : data.results ?? [];
}
