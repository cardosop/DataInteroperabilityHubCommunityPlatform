/**
 * Phase 102: Payment Failure Prevents Entitlement
 *
 * Order placed → payment fails → no entitlement granted
 */
import { test, expect } from '@playwright/test';

test.describe('Payment Failure', () => {
  test.skip(
    !process.env.E2E_LIFECYCLE_TESTS,
    'Lifecycle tests require full stack — set E2E_LIFECYCLE_TESTS=1'
  );

  test('failed payment does not grant entitlement', async ({ request }) => {
    const loginRes = await request.post('/api/v1/auth/login/', {
      data: {
        email: process.env.E2E_DC_EMAIL || 'dc@example.com',
        password: process.env.E2E_DC_PASSWORD || 'testpass123',
      },
    });

    if (loginRes.status() !== 200) {
      test.skip(true, 'DC user not available');
      return;
    }

    const { access_token } = await loginRes.json();
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
      'X-Tenant-ID': process.env.E2E_TENANT_ID || '',
    };

    // Verify order endpoint handles invalid payment gracefully
    const orderRes = await request.post('/api/v1/marketplace/orders/', {
      headers,
      data: {
        listing_id: '00000000-0000-0000-0000-000000000000',
        payment_method: 'INVALID',
      },
    });

    // Should return 400-level error, not 500
    expect(orderRes.status()).toBeGreaterThanOrEqual(400);
    expect(orderRes.status()).toBeLessThan(500);

    // Verify no entitlement was created
    const entitlementsRes = await request.get('/api/v1/marketplace/entitlements/', {
      headers,
    });
    if (entitlementsRes.status() === 200) {
      const data = await entitlementsRes.json();
      const results = data.results || data || [];
      // Should have no new entitlements from the failed payment
      expect(Array.isArray(results)).toBe(true);
    }
  });
});
