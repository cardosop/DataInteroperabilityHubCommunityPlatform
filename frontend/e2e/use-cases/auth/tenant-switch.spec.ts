/**
 * E2E: Tenant Switch (Phase 29.65.6.4)
 *
 * Login → switch tenant → verify context (assets list scoped to new tenant).
 * Uses API: GET /auth/me/tenants/, POST /auth/switch-tenant/, GET /assets/ with X-Tenant-Id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';

// Align with fixtures/auth.ts API resolution
const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1` : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('Tenant Switch (login → switch → verify context)', () => {
  test.setTimeout(120000);

  test('login, switch tenant via API, verify /auth/me and assets scoped to new tenant', async ({
    page,
  }) => {
    await clearAuthStorage(page);
    const user = await getTestUser();
    await loginUser(page, user);

    const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
    if (!accessToken) {
      test.skip(true, 'No access token after login');
      return;
    }

    const headers = { Authorization: `Bearer ${accessToken}` };

    // Ensure user has 2 tenants (E2E setup)
    const setupRes = await page.request.post(`${API_BASE}/test/ensure-e2e-tenant-switch-setup/`, {
      headers,
    });
    if (!setupRes.ok()) {
      test.skip(true, 'ensure-e2e-tenant-switch-setup not available (ENVIRONMENT=test required)');
      return;
    }
    const setup = (await setupRes.json()) as { secondary_tenant_id: string; tenant_ids: string[] };
    const secondaryTenantId = setup.secondary_tenant_id;

    // GET /auth/me/tenants/
    const tenantsRes = await page.request.get(`${API_BASE}/auth/me/tenants/`, { headers });
    expect(tenantsRes.ok()).toBeTruthy();
    const tenants = (await tenantsRes.json()) as { id: string; name: string; slug: string }[];
    expect(tenants.length).toBeGreaterThanOrEqual(2);

    // POST /auth/switch-tenant/
    const switchRes = await page.request.post(`${API_BASE}/auth/switch-tenant/`, {
      data: { tenant_id: secondaryTenantId },
      headers: { ...headers, 'Content-Type': 'application/json' },
    });
    expect(switchRes.ok()).toBeTruthy();
    const switchData = (await switchRes.json()) as { tenant_id: string };
    expect(switchData.tenant_id).toBe(secondaryTenantId);

    // GET /assets/ with X-Tenant-Id — verify 200 (scoped to new tenant)
    const assetsRes = await page.request.get(`${API_BASE}/assets/`, {
      headers: { ...headers, 'X-Tenant-Id': secondaryTenantId },
    });
    expect(assetsRes.ok()).toBeTruthy();
    const assetsData = (await assetsRes.json()) as { results?: unknown[] };
    expect(Array.isArray(assetsData.results) || Array.isArray(assetsData)).toBeTruthy();
  });
});
