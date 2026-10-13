/**
 * close-test-coverage-gaps 3.2 — fetchPublicPricing service contract
 * (285.13.11.2). Real service, only the API client mocked (the
 * CpoCostOverviewPage pattern).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fetchPublicPricing } from './pricingService';

const mockGet = vi.fn();

vi.mock('../../shared/api/client', () => ({
  apiClient: { getClient: () => ({ get: mockGet }) },
}));

describe('fetchPublicPricing', () => {
  beforeEach(() => {
    mockGet.mockReset();
  });

  it('GETs the public plans endpoint exactly', async () => {
    mockGet.mockResolvedValue({ data: { base_plans: [], ml_plans: [] } });
    await fetchPublicPricing();
    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(mockGet).toHaveBeenCalledWith('/api/v1/plans/public/');
  });

  it('returns the response data payload', async () => {
    const payload = {
      base_plans: [{ plan: { slug: 'free' }, tier_profile: null }],
      ml_plans: [],
    };
    mockGet.mockResolvedValue({ data: payload });
    await expect(fetchPublicPricing()).resolves.toBe(payload);
  });

  it('propagates a rejected request (the page renders the error state)', async () => {
    mockGet.mockRejectedValue(new Error('Network failure'));
    await expect(fetchPublicPricing()).rejects.toThrow('Network failure');
  });
});
