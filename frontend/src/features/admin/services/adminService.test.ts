/**
 * adminService tests — Phase 105
 */
import type { HttpClient } from '../../../shared/types/api';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { adminService } from './adminService';

describe('adminService', () => {
  let mock: HttpClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mock = apiClient.getClient();
  });

  it('listUsers calls GET on correct URL', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await adminService.listUsers();
    expect(vi.mocked(mock.get)).toHaveBeenCalled();
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('users');
  });

  it('handles network error gracefully', async () => {
    vi.mocked(mock.get).mockRejectedValue(new Error('Network Error'));
    await expect(adminService.listUsers()).rejects.toThrow('Network Error');
  });

  // close-test-coverage-gaps 4.1 — the cross-tenant feature-flag surface
  // was 404ing live: the service addressed the SELF-SERVICE family
  // (/tenants/{id}/feature-flags/ — the tenants URLconf only registers
  // me/feature-flags/) instead of the ADMIN endpoint mounted at
  // /api/v1/admin/ (tenants/admin_urls.py: admin-tenant-feature-flags +
  // admin-feature-flag-approval-approve). These URL pins hold the
  // corrected contract.
  it('getTenantFeatureFlags calls the ADMIN cross-tenant endpoint', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { flags: [] } });
    await adminService.getTenantFeatureFlags('tenant-uuid-1');
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toBe('/admin/tenants/tenant-uuid-1/feature-flags/');
  });

  it('updateTenantFeatureFlags PUTs the ADMIN cross-tenant endpoint', async () => {
    vi.mocked(mock.put).mockResolvedValue({ data: { flags: [] } });
    await adminService.updateTenantFeatureFlags('tenant-uuid-1', { data_mesh_enabled: true }, 'flip it');
    const [url, body] = vi.mocked(mock.put).mock.calls[0];
    expect(url).toBe('/admin/tenants/tenant-uuid-1/feature-flags/');
    expect(body).toEqual({ flags: { data_mesh_enabled: true }, reason: 'flip it' });
  });

  it('approveFeatureFlagFlip posts the ADMIN approval endpoint', async () => {
    vi.mocked(mock.post).mockResolvedValue({ data: { flag: {} } });
    await adminService.approveFeatureFlagFlip('approval-uuid-9');
    const url = vi.mocked(mock.post).mock.calls[0][0] as string;
    expect(url).toBe('/admin/feature-flag-approvals/approval-uuid-9/approve/');
  });

});
