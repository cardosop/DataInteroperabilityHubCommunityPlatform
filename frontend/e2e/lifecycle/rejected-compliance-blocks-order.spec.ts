/**
 * Lifecycle: Rejected Compliance Blocks Order (Phase 102, modernised in 225.4 P0.2).
 *
 * Tests the MVP fail-closed contract for marketplace orders:
 *   1. Ordering a non-existent listing returns 4xx (not 5xx) — API boundary check.
 *   2. Ordering with an invalid payload returns 4xx with validation details.
 *
 * Both verify that the API rejects invalid orders gracefully at the boundary,
 * not that a compliance scan was actually triggered and rejected.
 */
import { test, expect } from '../fixtures/test-data-cleanup';
import { getConsumerTestUser, loginViaApi } from '../fixtures/auth';

test.describe('Rejected Compliance Blocks Order', () => {
  test('order on non-existent listing returns 4xx (not 500)', async ({ request }) => {
    const consumer = await getConsumerTestUser();
    const { access_token } = await loginViaApi(consumer.email, consumer.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
    };

    // The all-zero UUID is a stable "definitely does not exist" marker.
    // The backend must reject the order with a 4xx, not 5xx.
    const orderRes = await request.post('/api/v1/marketplace/orders/', {
      headers,
      data: {
        listing_id: '00000000-0000-0000-0000-000000000000',
      },
    });

    expect(
      orderRes.status(),
      'Order on non-existent listing must return 4xx',
    ).toBeGreaterThanOrEqual(400);
    expect(orderRes.status()).toBeLessThan(500);

    // Verify error response is structured (not a bare 500 traceback)
    // intentional: best-effort .catch on an optional step — primary pass/fail is made by a downstream assertion (verifyViaApi, waitFor, explicit expect). The fallback value tolerates well-known transient or absent-UI cases without papering over real failures.
    const body = await orderRes.json().catch(() => null);
    expect(body, 'Error response must be parseable JSON').not.toBeNull();
  });

  test('order with missing listing_id returns validation error', async ({ request }) => {
    const consumer = await getConsumerTestUser();
    const { access_token } = await loginViaApi(consumer.email, consumer.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
    };

    // Empty payload — listing_id is required
    const orderRes = await request.post('/api/v1/marketplace/orders/', {
      headers,
      data: {},
    });

    expect(
      orderRes.status(),
      'Order with missing listing_id must return 4xx',
    ).toBeGreaterThanOrEqual(400);
    expect(orderRes.status()).toBeLessThan(500);
  });
});
