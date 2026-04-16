/**
 * Lifecycle: Failed DQ Blocks Publish (Phase 102, modernised in Phase 225.4 P0.2).
 *
 * DPO creates a DRAFT asset (no DQ run yet). Attempt to publish it to the
 * marketplace must be rejected at the API boundary — the MVP fail-closed
 * contract for DQ (MVP Group 5) is: a listing cannot be created for an
 * asset whose DQ has not passed.
 *
 * 225.4 changes:
 *   - Imports `test, expect` from the cleanup fixture (auto-teardown on
 *     success or failure; asset created here must never leak into the DB).
 *   - Uses `getTestUser()` (DATA_PROVIDER+TENANT_ADMIN fixture) and
 *     `loginViaApi`; replaces the old env-var credential pattern whose
 *     defaults (dpo@example.com) did not exist in any configured stack.
 *   - Drops the `E2E_LIFECYCLE_TESTS` opt-in guard — the spec is now part
 *     of the MVP CI run and must execute, not silently skip.
 */
import { test, expect } from '../fixtures/test-data-cleanup';
import { getTestUser, loginViaApi } from '../fixtures/auth';

test.describe('Failed DQ Blocks Publish', () => {
  test('listing creation is rejected for a DRAFT asset with no DQ run', async ({
    request,
    cleanup,
  }) => {
    const user = await getTestUser();
    const { access_token } = await loginViaApi(user.email, user.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
    };

    // Create DRAFT asset — no DQ run, so it is not publishable.
    const assetRes = await request.post('/api/v1/assets/', {
      headers,
      data: {
        key: `e2e-${cleanup.runId}-dq-fail-${Date.now()}`,
        name: 'E2E DQ Fail Test Asset',
        description: 'Created by failed-dq-blocks-publish lifecycle spec',
        visibility: 'INTERNAL',
      },
    });
    expect(
      assetRes.ok(),
      `asset create must succeed; got ${assetRes.status()} ${await assetRes.text()}`,
    ).toBe(true);

    const asset = (await assetRes.json()) as { id: string; status: string };
    cleanup.track({ type: 'asset', id: asset.id, owner: user });
    expect(asset.status).toBe('DRAFT');

    // Attempt to publish a listing for the DRAFT asset — MUST be rejected.
    const listingRes = await request.post('/api/v1/marketplace/listings/', {
      headers,
      data: {
        asset_id: asset.id,
        pricing_model: 'FREE',
      },
    });
    expect(
      listingRes.status(),
      'DRAFT asset with no DQ run must be rejected with a 4xx',
    ).toBeGreaterThanOrEqual(400);
    expect(listingRes.status()).toBeLessThan(500);
  });
});
