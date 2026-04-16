/**
 * Lifecycle: Revoked Entitlement (Phase 102, modernised in 225.4 P0.2).
 *
 * Sanity-level contract test: the entitlements endpoint is reachable for an
 * authenticated Data Consumer and never returns 5xx. Existence of a positive
 * "revocation denies access" case is deferred to the full value-chain spec,
 * which has the full listing→order→entitlement chain.
 *
 * 225.4 changes:
 *   - Imports `test, expect` from the cleanup fixture (no-op here; kept for
 *     consistency with the other lifecycle specs).
 *   - Uses `getConsumerTestUser()` + `loginViaApi`.
 *   - Drops the `E2E_LIFECYCLE_TESTS` opt-in guard.
 */
import { test, expect } from '../fixtures/test-data-cleanup';
import { getConsumerTestUser, loginViaApi } from '../fixtures/auth';

test.describe('Revoked Entitlement', () => {
  test('entitlements endpoint is reachable and returns a non-5xx', async ({ request }) => {
    const consumer = await getConsumerTestUser();
    const { access_token } = await loginViaApi(consumer.email, consumer.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
    };

    const entitlementsRes = await request.get('/api/v1/marketplace/entitlements/', {
      headers,
    });

    expect(entitlementsRes.status()).toBeLessThan(500);
  });
});
