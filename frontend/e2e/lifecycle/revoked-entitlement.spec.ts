/**
 * Lifecycle: Revoked Entitlement (Phase 102, modernised in 225.4 P0.2).
 *
 * Tests the entitlements API boundary:
 *   1. Entitlements endpoint is reachable and returns structured response.
 *   2. Requesting a non-existent entitlement returns 4xx (not 5xx).
 *
 * Full entitlement lifecycle (create → revoke → verify access denied) requires
 * the complete listing→order→entitlement chain which lives in the full-value-chain
 * spec and DPO/DC journey suites.
 */
import { test, expect } from '../fixtures/test-data-cleanup';
import { getConsumerTestUser, loginViaApi } from '../fixtures/auth';

test.describe('Revoked Entitlement', () => {
  test('entitlements endpoint returns structured response', async ({ request }) => {
    const consumer = await getConsumerTestUser();
    const { access_token } = await loginViaApi(consumer.email, consumer.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
    };

    const entitlementsRes = await request.get('/api/v1/marketplace/entitlements/', {
      headers,
    });

    // Must not return 5xx
    expect(
      entitlementsRes.status(),
      'Entitlements endpoint must not return 5xx',
    ).toBeLessThan(500);

    // If 200, verify the response is structured (not blank or malformed)
    if (entitlementsRes.ok()) {
      // intentional: best-effort .catch on an optional step — primary pass/fail is made by a downstream assertion (verifyViaApi, waitFor, explicit expect). The fallback value tolerates well-known transient or absent-UI cases without papering over real failures.
      const body = await entitlementsRes.json().catch(() => null);
      expect(body, 'Entitlements response must be valid JSON').not.toBeNull();
      // DRF pagination: { count, results: [] } or direct array
      const isArray = Array.isArray(body);
      const hasPagination = body && typeof body === 'object' && 'results' in body;
      expect(
        isArray || hasPagination,
        `Expected array or paginated response, got: ${JSON.stringify(body).slice(0, 200)}`,
      ).toBe(true);
    }
  });

  test('non-existent entitlement id returns 4xx (not 5xx)', async ({ request }) => {
    const consumer = await getConsumerTestUser();
    const { access_token } = await loginViaApi(consumer.email, consumer.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
    };

    const detailRes = await request.get(
      '/api/v1/marketplace/entitlements/00000000-0000-0000-0000-000000000000/',
      { headers }
    );

    // Must not return 5xx — should be 404 or 403
    expect(
      detailRes.status(),
      'Non-existent entitlement must return 4xx',
    ).toBeGreaterThanOrEqual(400);
    expect(detailRes.status()).toBeLessThan(500);
  });
});
