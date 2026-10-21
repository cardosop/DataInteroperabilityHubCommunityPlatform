/**
 * tenantSwitchService tests — 313.H.4 review.
 *
 * Pins the defensive array normalization in ``getMyTenants``: the
 * Header tenant switcher assumes an array, and a malformed payload
 * (object instead of array — schema drift or a proxy error shape)
 * used to crash the render with "tenants.find is not a function".
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { getMyTenants } from './tenantSwitchService';

describe('getMyTenants', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('returns the payload when it is an array', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: [{ id: 't1', name: 'Tenant One', slug: 'tenant-one' }],
    } as never);
    const tenants = await getMyTenants();
    expect(tenants).toEqual([{ id: 't1', name: 'Tenant One', slug: 'tenant-one' }]);
  });

  it('normalizes a malformed non-array payload to []', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: { t1: { name: 'Tenant One' } },
    } as never);
    const tenants = await getMyTenants();
    expect(tenants).toEqual([]);
  });
});
