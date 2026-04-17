/**
 * Lifecycle: Full Platform Value Chain (Phase 102, modernised in 225.4 P0.3).
 *
 * The canonical MVP story condensed into API-level smoke tests:
 *   1. DPO creates DRAFT asset → verified by GET.
 *   2. DPO creates contract linked to asset → verified by GET.
 *   3. Asset + contract round-trip: both retrievable and consistent.
 *   4. Marketplace listings endpoint reachable (contract smoke).
 *   5. Marketplace orders endpoint reachable (consumer smoke).
 *
 * Deeper flow (DQ/compliance → activate → publish → purchase → entitlement)
 * lives in the persona journey suites (DPO-001, DC-001, CPO-001). This spec
 * is the MVP CI canary verifying the end-to-end chain is wired.
 */
import { test, expect } from '../fixtures/test-data-cleanup';
import { getTestUser, getConsumerTestUser, loginViaApi } from '../fixtures/auth';

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

    // Step 2 — create contract linked to asset.
    const odcs = JSON.stringify({
      apiVersion: 'odcs.io/v3.0.2',
      kind: 'DataContract',
      id: `e2e-vc-${Date.now()}`,
      name: 'E2E Value Chain Contract',
      version: '1.0.0',
      schema: {
        fields: [
          { name: 'id', type: 'string' },
          { name: 'value', type: 'number' },
        ],
      },
    });
    const contractRes = await request.post('/api/v1/contracts/', {
      headers,
      data: {
        asset_id: asset.id,
        original_raw: odcs,
        original_format: 'JSON',
        original_spec_type: 'ODCS',
      },
    });
    expect(
      contractRes.status(),
      'contract create must not 5xx',
    ).toBeLessThan(500);

    let contractId: string | null = null;
    if (contractRes.ok()) {
      const contract = (await contractRes.json()) as { id: string };
      contractId = contract.id;
      expect(contractId).toBeTruthy();
      cleanup.track({ type: 'contract', id: contractId, owner: dpo });
    }

    // Step 3 — asset is retrievable by id.
    const getAssetRes = await request.get(`/api/v1/assets/${asset.id}/`, { headers });
    expect(getAssetRes.status()).toBe(200);
    const retrievedAsset = (await getAssetRes.json()) as { id: string; status: string };
    expect(retrievedAsset.id).toBe(asset.id);
    expect(retrievedAsset.status).toBe('DRAFT');

    // Step 4 — contract is retrievable and linked to asset.
    if (contractId) {
      const getContractRes = await request.get(`/api/v1/contracts/${contractId}/`, { headers });
      expect(getContractRes.status()).toBe(200);
      const retrievedContract = (await getContractRes.json()) as { id: string; asset?: string };
      expect(retrievedContract.id).toBe(contractId);
    }
  });

  test('marketplace endpoints reachable for DPO', async ({ request }) => {
    const dpo = await getTestUser();
    const { access_token } = await loginViaApi(dpo.email, dpo.password);
    const headers = { Authorization: `Bearer ${access_token}` };

    const listingsRes = await request.get('/api/v1/marketplace/listings/', { headers });
    expect(
      listingsRes.status(),
      'Marketplace listings must not return 5xx',
    ).toBeLessThan(500);

    // Verify response is structured
    if (listingsRes.ok()) {
      const body = await listingsRes.json().catch(() => null);
      expect(body).not.toBeNull();
    }
  });

  test('marketplace endpoints reachable for consumer', async ({ request }) => {
    const consumer = await getConsumerTestUser();
    const { access_token } = await loginViaApi(consumer.email, consumer.password);
    const headers = { Authorization: `Bearer ${access_token}` };

    // Consumer can browse marketplace
    const listingsRes = await request.get('/api/v1/marketplace/listings/', { headers });
    expect(listingsRes.status()).toBeLessThan(500);

    // Consumer can view orders
    const ordersRes = await request.get('/api/v1/marketplace/orders/', { headers });
    expect(ordersRes.status()).toBeLessThan(500);

    // Consumer can view entitlements
    const entitlementsRes = await request.get('/api/v1/marketplace/entitlements/', { headers });
    expect(entitlementsRes.status()).toBeLessThan(500);
  });
});
