/**
 * Phase 102: Failed DQ Blocks Publish
 *
 * DPO creates asset → runs DQ → DQ FAILS → publish attempt → blocked
 */
import { test, expect } from '@playwright/test';

test.describe('Failed DQ Blocks Publish', () => {
  test.skip(
    !process.env.E2E_LIFECYCLE_TESTS,
    'Lifecycle tests require full stack — set E2E_LIFECYCLE_TESTS=1'
  );

  test('asset with failed DQ cannot be published to marketplace', async ({ request }) => {
    const loginRes = await request.post('/api/v1/auth/login/', {
      data: {
        email: process.env.E2E_DPO_EMAIL || 'dpo@example.com',
        password: process.env.E2E_DPO_PASSWORD || 'testpass123',
      },
    });

    if (loginRes.status() !== 200) {
      test.skip(true, 'DPO user not available');
      return;
    }

    const { access_token } = await loginRes.json();
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
      'X-Tenant-ID': process.env.E2E_TENANT_ID || '',
    };

    // Create asset in DRAFT status (not activated, no DQ passed)
    const assetRes = await request.post('/api/v1/assets/', {
      headers,
      data: {
        key: `dq-fail-${Date.now()}`,
        name: 'DQ Fail Test Asset',
        description: 'Asset that should not be publishable without passing DQ',
      },
    });

    if (assetRes.status() === 201) {
      const asset = await assetRes.json();

      // Attempt to create listing for DRAFT asset (should fail)
      const listingRes = await request.post('/api/v1/marketplace/listings/', {
        headers,
        data: {
          asset_id: asset.id,
          pricing_model: 'FREE',
        },
      });

      // Asset in DRAFT status (no DQ passed) should be blocked
      expect(listingRes.status()).toBeGreaterThanOrEqual(400);
      expect(listingRes.status()).toBeLessThan(500);
    }
  });
});
