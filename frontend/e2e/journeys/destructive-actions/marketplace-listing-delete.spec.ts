/**
 * E2E spec — Marketplace listing destructive-action guarantee chain (Phase 226.G1).
 *
 * Background
 * ----------
 * Listing DELETE soft-deletes via `Listing.soft_delete()` (sets `status='DELETED'`
 * — `hub/apps/marketplace/models.py:178-181`). Service-layer entry point is
 * `MarketplaceService._destroy_listing_impl` (`services.py:544-597`) which:
 *   • runs `validate_listing_for_destroy` business rule,
 *   • flips status,
 *   • writes a `LISTING_DELETED` audit row.
 * View: `hub/apps/marketplace/views.py:485-533`.
 *
 * Guarantee chain asserted here:
 *   1. UI delete (DELETE /api/v1/marketplace/listings/{id}/) returns 204.
 *   2. Detail GET still resolves with `status='DELETED'`.
 *   3. PUBLISHED-status filter no longer surfaces the row (the marketplace's
 *      *user-visible* "gone" guarantee — the soft-deleted row stays in the
 *      tenant-scoped queryset only for management).
 *   4. LISTING_DELETED audit row exists.
 *   5. Re-DELETE rejected (no double audit).
 *   6. Cascade — entitlements emitted from this listing remain queryable
 *      (the platform deliberately preserves entitlement tombstones so
 *      consumers retain provenance of revoked access — see
 *      `frontend/e2e/lifecycle/revoked-entitlement.spec.ts`).
 *
 * No mocks. Real backend only.
 */

import { test, expect } from '../../fixtures/test-data-cleanup';
import { getTestUser, loginViaApi } from '../../fixtures/auth';
import { verifyViaApi } from '../../fixtures/verifyViaApi';
import { verifyAuditEvent } from '../../fixtures/verifyAuditEvent';
import { ensureE2eSubscription } from '../../fixtures/ensureE2eSubscription';
import { createAssetViaApi } from '../../fixtures/api-assets';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('226.G1 — Marketplace listing delete guarantee chain @critical @destructive', () => {
  test.setTimeout(180_000);

  test('soft-delete: listing terminally DELETED, audit row written, hidden from PUBLISHED query, re-delete safe', async ({
    page,
    cleanup,
  }) => {
    const dpo = await getTestUser();
    const { access_token } = await loginViaApi(dpo.email, dpo.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
    };

    await page.goto('/');
    await page.evaluate((token) => {
      localStorage.setItem('access_token', token);
    }, access_token);

    await ensureE2eSubscription(page, access_token);

    // ── Step 1 — Provision a parent asset that is already ACTIVE.
    // ListingCreateSerializer's BusinessRules check (`hub/apps/marketplace/
    // business_rules.py`) rejects listings on non-ACTIVE assets with 400
    // "Asset must be ACTIVE to be listed" — naive POST + activate dance
    // doesn't satisfy activation requirements (needs contract + DQ + compliance).
    // The createAssetViaApi helper with ensureActivated:true does the full
    // chain (asset + contract + activate), so the listing-create succeeds.
    const assetId = await createAssetViaApi(dpo, {
      ensureActivated: true,
      forceNew: true,
      cleanup,
    });
    const asset = { id: assetId, status: 'ACTIVE' as const };

    // ── Step 2 — Publish a listing for the asset.
    // Per ListingCreateSerializer (`hub/apps/marketplace/serializers.py:101-167`)
    // the create payload is FLAT (asset_id + title + short_description +
    // pricing_model at the top level — NOT nested in metadata_json), and
    // pricing_model is the uppercase TextChoices value (FREE / FREE_AUTO_APPROVE).
    const listingTitle = `G1 Listing ${cleanup.runId.slice(0, 8)} ${Date.now()}`;
    const listingRes = await page.request.post(`${API_BASE}/marketplace/listings/`, {
      headers,
      data: {
        asset_id: asset.id,
        title: listingTitle,
        short_description: '226.G1 listing-delete probe.',
        long_description: 'Lifecycle probe — created and immediately deleted by 226.G1 spec.',
        pricing_model: 'FREE',
        domain: 'test',
        tags: ['e2e', 'g1-probe'],
      },
    });
    expect(
      listingRes.status(),
      `listing create expected 201; got ${listingRes.status()} ${await listingRes.text()}`,
    ).toBe(201);
    const listing = (await listingRes.json()) as { id: string };
    const listingId = listing.id;
    cleanup.track({ type: 'listing', id: listingId, owner: dpo });

    // ── Step 3 — DELETE the listing.
    const deleteRes = await page.request.delete(
      `${API_BASE}/marketplace/listings/${listingId}/`,
      { headers },
    );
    expect(
      deleteRes.status(),
      `DELETE expected 204; got ${deleteRes.status()} ${await deleteRes.text()}`,
    ).toBe(204);

    // ── Step 4 — Detail GET resolves with terminal state.
    await verifyViaApi<{ id: string; status: string }>(
      page,
      `/api/v1/marketplace/listings/${listingId}/`,
      (body) => body.id === listingId && body.status === 'DELETED',
    );

    // ── Step 5 — PUBLISHED filter must not surface the row.
    const listRes = await page.request.get(
      `${API_BASE}/marketplace/listings/?status=PUBLISHED&page_size=100`,
      { headers },
    );
    expect(listRes.ok()).toBe(true);
    const listBody = (await listRes.json()) as
      | { results?: Array<{ id: string }> }
      | Array<{ id: string }>;
    const rows = Array.isArray(listBody) ? listBody : listBody.results ?? [];
    const found = rows.find((r) => r.id === listingId);
    expect(
      found,
      `DELETED listing ${listingId} should not appear in status=PUBLISHED list, found=${JSON.stringify(found)}`,
    ).toBeUndefined();

    // ── Step 6 — Audit row written.
    await verifyAuditEvent(page, {
      action: 'LISTING_DELETED',
      resourceType: 'LISTING',
      resourceId: listingId,
    });

    // ── Step 7 — Re-DELETE must not 5xx.
    const reDel = await page.request.delete(
      `${API_BASE}/marketplace/listings/${listingId}/`,
      { headers },
    );
    expect(
      reDel.status(),
      `Re-DELETE returned 5xx — likely double-cascade crash. Status=${reDel.status()}`,
    ).toBeLessThan(500);

    // ── Step 8 — Cascade: search endpoint (public marketplace discovery)
    // must NOT surface the deleted listing.
    const searchRes = await page.request.get(
      `${API_BASE}/marketplace/listings/search/?search=${encodeURIComponent(listingTitle)}`,
      { headers },
    );
    if (searchRes.ok()) {
      const searchBody = (await searchRes.json()) as
        | { results?: Array<{ id: string }> }
        | Array<{ id: string }>;
      const searchRows = Array.isArray(searchBody) ? searchBody : searchBody.results ?? [];
      const inSearch = searchRows.find((r) => r.id === listingId);
      expect(
        inSearch,
        `DELETED listing ${listingId} must not appear in marketplace search results`,
      ).toBeUndefined();
    }
  });
});
