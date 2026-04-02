/**
 * E2E Test: GDPR Data Deletion — Erasure requests endpoint smoke test
 *
 * Verifies the GDPR erasure requests endpoint is reachable and does not return 5xx.
 * Gated behind E2E_JOURNEYS env var; skips gracefully when test env is unavailable.
 */
import { test, expect } from '@playwright/test';

test.describe('[GDPR Data Deletion] Journey', () => {
  test.skip(!process.env.E2E_JOURNEYS, 'Set E2E_JOURNEYS=1 to run');

  test('gdpr data deletion happy path — erasure requests returns non-500', async ({ request }) => {
    const loginRes = await request.post('/api/v1/auth/login/', {
      data: {
        email: process.env.E2E_USER_EMAIL || 'admin@example.com',
        password: process.env.E2E_USER_PASSWORD || 'testpass123',
      },
    });
    if (loginRes.status() !== 200) {
      test.skip(true, 'Test user not available');
      return;
    }
    const { access_token } = await loginRes.json();
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
      'X-Tenant-ID': process.env.E2E_TENANT_ID || '',
    };

    const res = await request.get('/api/v1/gdpr/erasure-requests/', { headers });
    expect(res.status()).toBeLessThan(500);
  });
});
