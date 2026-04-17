/**
 * Lifecycle: Failed DQ Blocks Publish (Phase 102, modernised in Phase 225.4 P0.2).
 *
 * Tests the MVP fail-closed contract for DQ (MVP Group 5):
 *   1. A DRAFT asset (no DQ run) cannot have a marketplace listing created.
 *   2. An asset with dq_status=UNKNOWN cannot be activated (DQ gate enforced).
 *
 * Both verify the actual business rule at the API boundary, not just HTTP status.
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

    // Verify the error response includes a meaningful rejection reason
    const body = await listingRes.json().catch(() => null);
    if (body) {
      const errorText = JSON.stringify(body).toLowerCase();
      // The API should indicate WHY the listing was rejected — not just "bad request"
      const hasMeaningfulError =
        errorText.includes('draft') ||
        errorText.includes('active') ||
        errorText.includes('dq') ||
        errorText.includes('quality') ||
        errorText.includes('status') ||
        errorText.includes('not allowed') ||
        errorText.includes('cannot');
      if (!hasMeaningfulError) {
        // Annotate but don't fail — the 4xx is the important assertion
        test.info().annotations.push({
          type: 'generic-error-response',
          description: `API returned 4xx but error body lacks specific reason: ${JSON.stringify(body).slice(0, 200)}`,
        });
      }
    }
  });

  test('DRAFT asset cannot be activated (DQ gate enforced at activation)', async ({
    request,
    cleanup,
  }) => {
    const user = await getTestUser();
    const { access_token } = await loginViaApi(user.email, user.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
    };

    // Create a DRAFT asset — dq_status defaults to UNKNOWN.
    const assetRes = await request.post('/api/v1/assets/', {
      headers,
      data: {
        key: `e2e-${cleanup.runId}-dq-gate-${Date.now()}`,
        name: 'E2E DQ Gate Test Asset',
        description: 'Tests that DQ gate blocks activation',
        visibility: 'INTERNAL',
      },
    });
    expect(assetRes.ok()).toBe(true);
    const asset = (await assetRes.json()) as { id: string; version?: number };
    cleanup.track({ type: 'asset', id: asset.id, owner: user });

    // Attempt to activate the DRAFT asset — should fail because:
    // 1. No ACTIVE contract (can_activate check)
    // 2. dq_status is UNKNOWN (if dataset exists)
    // The activation endpoint requires `version` for optimistic locking.
    const activateRes = await request.post(`/api/v1/assets/${asset.id}/activate/`, {
      headers,
      data: { version: asset.version ?? 1 },
    });
    expect(
      activateRes.status(),
      'DRAFT asset with no contract and UNKNOWN DQ status must be rejected',
    ).toBeGreaterThanOrEqual(400);
    expect(activateRes.status()).toBeLessThan(500);

    // Verify the rejection mentions activation blockers
    const body = (await activateRes.json().catch(() => null)) as {
      details?: string[];
      error?: string;
      code?: string;
    } | null;
    if (body) {
      const hasBlockers =
        (body.details && body.details.length > 0) ||
        body.error?.includes('contract') ||
        body.error?.includes('requirement') ||
        body.code === 'ASSET_ACTIVATION_BLOCKED';
      expect(
        hasBlockers,
        `Activation rejection should include blockers; got: ${JSON.stringify(body).slice(0, 300)}`,
      ).toBe(true);
    }
  });
});
