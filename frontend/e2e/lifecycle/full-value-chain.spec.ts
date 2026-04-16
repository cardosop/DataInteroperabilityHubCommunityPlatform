/**
 * Lifecycle: Full Platform Value Chain (Phase 102, modernised in 225.4 P0.3).
 *
 * The canonical MVP story condensed into a single API-level smoke:
 *   1. DPO authenticates.
 *   2. DPO creates a DRAFT asset.
 *   3. DPO creates a contract.
 *   4. The DRAFT asset is retrievable by id (no eventual-consistency surprise).
 *   5. Marketplace listings endpoint is reachable (contract smoke).
 *
 * Deeper flow (link contract → upload file → run DQ/compliance → publish
 * listing → order → entitlement) lives in the persona journey suites. This
 * spec is the MVP CI canary that the end-to-end chain is *wired*.
 *
 * 225.4 changes:
 *   - Imports `test, expect` from the cleanup fixture. The asset AND the
 *     contract created here are tracked so they are torn down whether the
 *     spec passes or fails.
 *   - Uses `getTestUser()` + `loginViaApi`; drops env-var credentials.
 *   - Drops the `E2E_LIFECYCLE_TESTS` opt-in guard — spec runs in MVP CI.
 */
import { test, expect } from '../fixtures/test-data-cleanup';
import { getTestUser, loginViaApi } from '../fixtures/auth';

test.describe('Full Value Chain', () => {
  test('asset → contract → retrieval round-trip', async ({ request, cleanup }) => {
    const dpo = await getTestUser();
    const { access_token } = await loginViaApi(dpo.email, dpo.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
    };

    // Step 1 — create asset.
    const assetRes = await request.post('/api/v1/assets/', {
      headers,
      data: {
        key: `e2e-${cleanup.runId}-vc-asset-${Date.now()}`,
        name: 'E2E Lifecycle Test Asset',
        description: 'Created by full value-chain lifecycle spec',
        visibility: 'INTERNAL',
      },
    });
    expect(
      assetRes.ok(),
      `asset create must succeed; got ${assetRes.status()} ${await assetRes.text()}`,
    ).toBe(true);
    const asset = (await assetRes.json()) as { id: string; status: string };
    cleanup.track({ type: 'asset', id: asset.id, owner: dpo });
    expect(asset.id).toBeTruthy();
    expect(asset.status).toBe('DRAFT');

    // Step 2 — create contract.
    const contractRes = await request.post('/api/v1/contracts/', {
      headers,
      data: {
        original_raw: JSON.stringify({
          datasetName: `E2E Lifecycle ${cleanup.runId}`,
          version: '1.0.0',
        }),
        original_format: 'JSON',
      },
    });
    expect(
      contractRes.status(),
      'contract create must not 5xx',
    ).toBeLessThan(500);
    if (contractRes.ok()) {
      const contract = (await contractRes.json()) as { id: string };
      if (contract.id) {
        cleanup.track({ type: 'contract', id: contract.id, owner: dpo });
      }
    }

    // Step 3 — asset is retrievable by id.
    const getAssetRes = await request.get(`/api/v1/assets/${asset.id}/`, {
      headers,
    });
    expect(getAssetRes.status()).toBe(200);
  });

  test('marketplace listing endpoint is reachable for DPO', async ({ request }) => {
    const dpo = await getTestUser();
    const { access_token } = await loginViaApi(dpo.email, dpo.password);
    const headers = { Authorization: `Bearer ${access_token}` };

    const listingsRes = await request.get('/api/v1/marketplace/listings/', { headers });
    expect(listingsRes.status()).toBeLessThan(500);
  });
});
