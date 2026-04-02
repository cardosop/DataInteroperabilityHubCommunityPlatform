/**
 * Capabilities service unit tests — OpenAPI fetch retry and fallback behavior.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockGet = vi.fn();

vi.mock('../../../shared/api/client', () => ({
  apiClient: {
    getClient: () => ({ get: mockGet }),
  },
}));

import { capabilitiesService } from './capabilitiesService';

describe('capabilitiesService.loadCapabilities', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('retries once when the first OpenAPI request fails', async () => {
    mockGet
      .mockRejectedValueOnce(new Error('transient network'))
      .mockResolvedValueOnce({
        data: { paths: { '/api/v1/auth/register/': {} } },
      });

    const caps = await capabilitiesService.loadCapabilities(true);

    expect(mockGet).toHaveBeenCalledTimes(2);
    expect(caps['auth.register']?.available).toBe(true);
  });
});
