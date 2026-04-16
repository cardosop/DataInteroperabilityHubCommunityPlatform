/**
 * Lifecycle: Rejected Compliance Blocks Order (Phase 102, modernised in 225.4 P0.2).
 *
 * A Data Consumer attempt to place an order against a non-existent listing
 * must be rejected at the API boundary (no silent 500, no data leak). This
 * is the negative side of the marketplace-order flow that MVP Group 7
 * specifies as fail-closed.
 *
 * 225.4 changes:
 *   - Imports `test, expect` from the cleanup fixture (no resources are
 *     created here — the fixture stays idle, costs nothing).
 *   - Uses `getConsumerTestUser()` + `loginViaApi` instead of env-var
 *     credentials whose fallbacks (dc@example.com) didn't exist.
 *   - Drops the `E2E_LIFECYCLE_TESTS` opt-in guard so the spec runs in
 *     MVP CI instead of silently skipping.
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

    // The all-zero UUID is a stable "definitely does not exist" marker that
    // also acts as a proxy for "compliance-rejected listing" — in either
    // case the backend must reject the order with a 4xx, not 5xx.
    const orderRes = await request.post('/api/v1/marketplace/orders/', {
      headers,
      data: {
        listing_id: '00000000-0000-0000-0000-000000000000',
      },
    });

    expect(orderRes.status()).toBeGreaterThanOrEqual(400);
    expect(orderRes.status()).toBeLessThan(500);
  });
});
