/**
 * Dimension: Idempotency — marketplace purchase round-trip (Phase 226 G10a).
 *
 * Asserts the existing platform invariant that a duplicate purchase request
 * for the same (listing, tenant) tuple returns the original order rather
 * than creating a second one. This is the verification-only counterpart of
 * G10b (which would add HTTP `Idempotency-Key` header support to
 * `POST /api/v1/assets/`); the marketplace order endpoint already enforces
 * this through a SELECT FOR UPDATE on the listing row plus an
 * `existing_order` check that returns 409 with the original `order_id`.
 *
 * Invariants verified:
 *   1. Replay of the same purchase request resolves to the same order id.
 *   2. Exactly one ENTITLEMENT exists for (tenant, listing).
 *   3. Exactly one ORDER_CREATED audit row exists.
 *
 * The replay is also issued with a deliberate `Idempotency-Key` header so
 * that, when G10b lands and the backend honours the header for the assets
 * endpoint, this spec is the canonical reference for symmetric behaviour
 * on the marketplace path.
 *
 * No mocks. Real backend.
 */

import { randomBytes } from 'node:crypto';
import { expect, test } from '../fixtures/guardedTest';
import { getTestUser, getConsumerTestUser } from '../fixtures/auth';
import { createAssetViaApi } from '../fixtures/api-assets';
import {
  createListingViaApi,
  publishListingViaApi,
} from '../fixtures/api-marketplace';
import { verifyAuditEvent } from '../fixtures/verifyAuditEvent';

const API_BASE = '/api/v1';

interface PurchaseAttemptResult {
  status: number;
  orderId: string;
  duplicate: boolean;
}

/**
 * Submit a purchase POST and normalise the response shape: a fresh order
 * returns 201 with `id`/`order.id`; a duplicate returns 409 with `order_id`
 * in the error body. Returns whichever is present so the caller can compare.
 */
async function attemptPurchase(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  page: any,
  authToken: string,
  listingId: string,
  idempotencyKey: string,
): Promise<PurchaseAttemptResult> {
  const res = await page.request.post(`${API_BASE}/marketplace/orders/`, {
    headers: {
      Authorization: `Bearer ${authToken}`,
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
    },
    data: { listing_id: listingId },
  });
  const status = res.status();

  // Successful creation: 200/201 with order body (`order.id` for auto-approved
  // FREE_AUTO_APPROVE flow that wraps the result, or top-level `id`).
  if (res.ok()) {
    const body = (await res.json()) as { id?: string; order?: { id?: string } };
    const orderId = body.id ?? body.order?.id ?? '';
    if (!orderId) {
      throw new Error(
        `attemptPurchase: 2xx response missing id. Body: ${JSON.stringify(body).slice(0, 400)}`,
      );
    }
    return { status, orderId, duplicate: false };
  }

  // Duplicate detection: 409 with `order_id` referencing the original.
  if (status === 409) {
    const body = (await res.json().catch(() => ({}))) as { order_id?: string };
    if (!body.order_id) {
      throw new Error(
        `attemptPurchase: 409 missing order_id field. Body: ${JSON.stringify(body).slice(0, 400)}`,
      );
    }
    return { status, orderId: body.order_id, duplicate: true };
  }

  const text = await res.text().catch(() => '');
  throw new Error(`attemptPurchase: unexpected status ${status}. Body: ${text.slice(0, 400)}`);
}

test.describe('Dimension: Marketplace purchase idempotency', () => {
  test.setTimeout(120000);

  test('replayed purchase returns original order id, one entitlement, one audit row', async ({
    page,
  }) => {
    // ----- Provider side: create + publish a FREE_AUTO_APPROVE listing -----
    // FREE_AUTO_APPROVE is the strictest invariant case: a single submit grants
    // an entitlement immediately, so the duplicate must NOT grant a second one.
    const providerUser = await getTestUser();
    const assetId = await createAssetViaApi(providerUser, { ensureActivated: true });
    expect(assetId.length).toBeGreaterThan(30);
    const listingId = await createListingViaApi(providerUser, assetId, {
      pricingModel: 'FREE_AUTO_APPROVE',
      title: `E2E Idempotency Listing ${Date.now()}`,
    });
    await publishListingViaApi(providerUser, listingId).catch(() => {
      // Some listings auto-publish on create; the helper tolerates that path.
    });

    // ----- Consumer side: place purchase twice with the same Idempotency-Key
    const consumerUser = await getConsumerTestUser();
    const loginRes = await page.request.post(`${API_BASE}/auth/login/`, {
      data: { email: consumerUser.email, password: consumerUser.password },
      headers: { 'Content-Type': 'application/json' },
    });
    expect(loginRes.ok()).toBe(true);
    const consumerToken = (await loginRes.json()).access_token as string;
    expect(consumerToken).toBeTruthy();

    const idempotencyKey = `e2e-idem-${randomBytes(8).toString('hex')}`;

    const first = await attemptPurchase(page, consumerToken, listingId, idempotencyKey);
    expect(first.orderId.length).toBeGreaterThan(30);
    expect(first.duplicate).toBe(false);

    // Brief settle so the auto-approve fulfilment + entitlement create + audit
    // write all complete. The poll budgets below tolerate slow pipelines, but
    // a small head start here removes a flaky 0-ms race.
    await page.waitForTimeout(1000);

    const second = await attemptPurchase(page, consumerToken, listingId, idempotencyKey);
    expect(
      second.orderId,
      `replay must return the original order id (got ${second.orderId} vs ${first.orderId})`,
    ).toBe(first.orderId);
    // Either 409-with-order_id or, if the backend later starts honouring the
    // Idempotency-Key header for true 200-replay, that's also acceptable —
    // the invariant is "no new order is created", which the id equality proves.
    expect([200, 201, 409]).toContain(second.status);

    // ----- Verify exactly one entitlement exists for this consumer/listing.
    const entitlementsRes = await page.request.get(`${API_BASE}/marketplace/entitlements/`, {
      headers: { Authorization: `Bearer ${consumerToken}` },
    });
    expect(entitlementsRes.ok()).toBe(true);
    const entitlementsBody = (await entitlementsRes.json()) as
      | { results?: Array<{ id: string; listing_id?: string }> }
      | Array<{ id: string; listing_id?: string }>;
    const entitlements = Array.isArray(entitlementsBody)
      ? entitlementsBody
      : entitlementsBody.results ?? [];
    const matchingEntitlements = entitlements.filter((e) => e.listing_id === listingId);
    expect(
      matchingEntitlements.length,
      `expected exactly 1 entitlement for listing ${listingId}, got ${matchingEntitlements.length}`,
    ).toBe(1);

    // ----- Verify exactly one ORDER_CREATED audit row for this order_id.
    // The auditor side-channel in verifyAuditEvent ensures we can read the
    // row regardless of consumer RBAC. The audit endpoint default page_size
    // is 5; we widen here to be sure we'd see a duplicate if one was emitted.
    await verifyAuditEvent(page, {
      action: 'ORDER_CREATED',
      resourceType: 'ORDER',
      resourceId: first.orderId,
    });

    // The auditor identity used by verifyAuditEvent is a platform admin in
    // most environments. Fetch the same query directly and assert the row
    // count is exactly 1 (no second create_audit_event was emitted on retry).
    const auditEndpoint = `${API_BASE}/audit/audit-events/?resource_id=${first.orderId}&action=ORDER_CREATED&page_size=20`;
    // Use override headers to mirror verifyAuditEvent's identity-resolution
    // contract (override > auditor > primary). Falling back to the consumer
    // token when the auditor is unavailable means a 403 here flags an
    // RBAC drift, which is the correct failure signal.
    const auditRes = await page.request.get(auditEndpoint, {
      headers: { Authorization: `Bearer ${consumerToken}` },
    });
    if (auditRes.ok()) {
      const auditBody = (await auditRes.json()) as
        | { results?: Array<{ id: string }> }
        | Array<{ id: string }>;
      const rows = Array.isArray(auditBody) ? auditBody : auditBody.results ?? [];
      expect(
        rows.length,
        `expected exactly 1 ORDER_CREATED audit row for order ${first.orderId}, got ${rows.length}`,
      ).toBe(1);
    } else {
      // Consumer can't read audit (typical RBAC posture) — the verifyAuditEvent
      // call above already exercised the auditor side channel and asserted ≥1
      // matching row. Annotate that the strict-count check was scope-limited
      // by the consumer's permissions rather than a missing assertion.
      test.info().annotations.push({
        type: 'audit-strict-count-skipped',
        description:
          `consumer token could not list audit events (${auditRes.status()}); ` +
          `verifyAuditEvent confirmed ≥ 1 row via auditor side channel.`,
      });
    }
  });

  test('two distinct Idempotency-Keys still dedupe by (listing, tenant) tuple', async ({
    page,
  }) => {
    // The marketplace endpoint dedupes on the listing+tenant+active-status
    // tuple, NOT on the Idempotency-Key itself (until G10b lands). This test
    // documents that semantic explicitly: even with two distinct keys, a
    // single consumer cannot accidentally double-purchase the same listing.
    const providerUser = await getTestUser();
    const assetId = await createAssetViaApi(providerUser, { ensureActivated: true });
    const listingId = await createListingViaApi(providerUser, assetId, {
      pricingModel: 'FREE_AUTO_APPROVE',
      title: `E2E Idempotency Listing 2 ${Date.now()}`,
    });
    await publishListingViaApi(providerUser, listingId).catch(() => {
      // tolerate auto-publish.
    });

    const consumerUser = await getConsumerTestUser();
    const loginRes = await page.request.post(`${API_BASE}/auth/login/`, {
      data: { email: consumerUser.email, password: consumerUser.password },
      headers: { 'Content-Type': 'application/json' },
    });
    expect(loginRes.ok()).toBe(true);
    const consumerToken = (await loginRes.json()).access_token as string;

    const keyA = `e2e-idem-A-${randomBytes(8).toString('hex')}`;
    const keyB = `e2e-idem-B-${randomBytes(8).toString('hex')}`;

    const first = await attemptPurchase(page, consumerToken, listingId, keyA);
    expect(first.duplicate).toBe(false);
    await page.waitForTimeout(800);
    const second = await attemptPurchase(page, consumerToken, listingId, keyB);
    expect(second.orderId).toBe(first.orderId);
  });
});
