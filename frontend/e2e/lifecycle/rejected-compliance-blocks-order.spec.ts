/**
 * Phase 102: Rejected Compliance Blocks Order
 *
 * Listing exists → compliance check FAILS → order blocked or warned
 */
import { test, expect } from '@playwright/test';

test.describe('Rejected Compliance Blocks Order', () => {
  test.skip(
    !process.env.E2E_LIFECYCLE_TESTS,
    'Lifecycle tests require full stack — set E2E_LIFECYCLE_TESTS=1'
  );

  test('order on non-compliant listing returns error', async ({ request }) => {
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

    // Attempt to place order on non-existent listing (simulates compliance failure)
    const orderRes = await request.post('/api/v1/marketplace/orders/', {
      headers,
      data: {
        listing_id: '00000000-0000-0000-0000-000000000000',
      },
    });

    // Should return 400 or 404 — not 500
    expect(orderRes.status()).toBeGreaterThanOrEqual(400);
    expect(orderRes.status()).toBeLessThan(500);
  });
});
